from datetime import date

import pytest

from app.ingestion.base_parser import ParsedStatement, StatementParseError
from app.ingestion.csv_parser import MAX_DATA_ROWS, MAX_ROW_AMOUNT_MINOR, GenericCsvParser
from app.ingestion.drift_guard import compute_layout_fingerprint

FILENAME = "statement.csv"
DEFAULT_HEADER = "Date,Description,Debit,Credit,Balance"
SPLIT_HEADER = "Date,Description,Debit,Credit"


def _csv(*lines: str, header: str = DEFAULT_HEADER) -> bytes:
    return "\n".join((header, *lines)).encode("utf-8") + b"\n"


def _parse(*lines: str, header: str = DEFAULT_HEADER) -> ParsedStatement:
    return GenericCsvParser().parse(_csv(*lines, header=header), FILENAME)


def test_parser_reports_generic_csv_name_and_version():
    # Arrange
    parser = GenericCsvParser()

    # Act / Assert
    assert parser.name == "generic_csv"
    assert parser.version == "1"


def test_parse_returns_metadata_and_layout_fingerprint_for_headers():
    # Arrange / Act
    statement = _parse("01/03/2026,Coffee,50.00,,950.00")

    # Assert
    assert statement.parser_name == "generic_csv"
    assert statement.parser_version == "1"
    assert statement.institution is None
    assert statement.account_number_masked is None
    assert statement.layout_fingerprint == compute_layout_fingerprint(
        ["date", "description", "debit", "credit", "balance"], None
    )


@pytest.mark.parametrize(
    "header",
    [
        "Date,Description,Debit,Credit,Balance",
        "Txn Date,Narration,Withdrawal,Deposit,Running Balance",
        "Transaction Date,Particulars,Withdrawal Amt,Deposit Amt,Closing Balance",
        "Value Date,Remarks,DR,CR,Balance",
    ],
)
def test_accepts_each_header_alias_family(header):
    # Arrange
    line = "01/03/2026,UPI payment,100.00,,1000.00"

    # Act
    statement = _parse(line, header=header)

    # Assert
    assert statement.rows[0].raw_description == "UPI payment"
    assert statement.rows[0].debit_minor == 10000
    assert statement.rows[0].credit_minor == 0
    assert statement.rows[0].stated_running_balance_minor == 100000


def test_header_matching_ignores_case_and_extra_whitespace():
    # Arrange
    header = "  DATE ,  txn   DATE  , NARRATION, debit ,CREDIT"

    # Act
    statement = _parse("01/03/2026,01/03/2026,Coffee,50.00,", header=header)

    # Assert
    assert statement.rows[0].tx_date == date(2026, 3, 1)
    assert statement.rows[0].debit_minor == 5000


def test_signed_amount_column_maps_negative_to_debit_and_positive_to_credit():
    # Arrange
    header = "Date,Narration,Amount,Balance"

    # Act
    statement = _parse(
        "01/03/2026,Salary,5000.00,6000.00",
        "02/03/2026,Rent,-1200.00,4800.00",
        header=header,
    )

    # Assert
    salary, rent = statement.rows
    assert (salary.credit_minor, salary.debit_minor) == (500000, 0)
    assert (rent.credit_minor, rent.debit_minor) == (0, 120000)


@pytest.mark.parametrize(
    "date_text",
    ["14/03/2026", "14-03-2026", "2026-03-14", "14-Mar-2026", "14 Mar 2026", "14/03/26"],
)
def test_accepts_each_supported_date_format(date_text):
    # Arrange / Act
    statement = _parse(f"{date_text},Coffee,50.00,", header=SPLIT_HEADER)

    # Assert
    assert statement.rows[0].tx_date == date(2026, 3, 14)


def test_dates_are_parsed_day_first():
    # Arrange / Act
    statement = _parse("03/04/2026,Coffee,50.00,", header=SPLIT_HEADER)

    # Assert
    assert statement.rows[0].tx_date == date(2026, 4, 3)


def test_unparseable_date_error_names_the_data_row():
    # Arrange
    content = _csv("01/03/2026,Ok,1.00,", "2026/03/14,Bad,1.00,", header=SPLIT_HEADER)

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_BAD_DATE: data row 2"):
        GenericCsvParser().parse(content, FILENAME)


@pytest.mark.parametrize(
    ("amount_text", "expected_minor"),
    [
        ("1,23,456.78", 12345678),
        ("₹500", 50000),
        ("INR 1,000.50", 100050),
        ("Rs. 250", 25000),
        ("  75  ", 7500),
        ("1,000.00 Cr", 100000),
        ("250.00Dr", 25000),
    ],
)
def test_amount_clean_ups_convert_to_minor_units(amount_text, expected_minor):
    # Arrange / Act
    statement = _parse(f'01/03/2026,Test,"{amount_text}",', header=SPLIT_HEADER)

    # Assert
    assert statement.rows[0].debit_minor == expected_minor
    assert statement.rows[0].credit_minor == 0


def test_empty_amount_cell_counts_as_zero():
    # Arrange / Act
    statement = _parse("01/03/2026,Refund,,40.00", header=SPLIT_HEADER)

    # Assert
    assert statement.rows[0].debit_minor == 0
    assert statement.rows[0].credit_minor == 4000


def test_descending_file_is_reversed_to_chronological_order():
    # Arrange: opening 1000.00; 13th +500, 14th -200, 15th -100
    lines = (
        "15/03/2026,Third,100.00,,1200.00",
        "14/03/2026,Second,200.00,,1300.00",
        "13/03/2026,First,,500.00,1500.00",
    )

    # Act
    statement = _parse(*lines)

    # Assert
    assert [row.raw_description for row in statement.rows] == ["First", "Second", "Third"]
    assert [row.row_index for row in statement.rows] == [0, 1, 2]
    assert [row.page_number for row in statement.rows] == [1, 1, 1]
    assert statement.statement_start_date == date(2026, 3, 13)
    assert statement.statement_end_date == date(2026, 3, 15)
    assert statement.opening_balance_minor == 100000
    assert statement.closing_balance_minor == 120000


def test_ascending_file_keeps_file_order():
    # Arrange / Act
    statement = _parse(
        "13/03/2026,First,,500.00,1500.00",
        "14/03/2026,Second,200.00,,1300.00",
    )

    # Assert
    assert [row.raw_description for row in statement.rows] == ["First", "Second"]
    assert [row.row_index for row in statement.rows] == [0, 1]


def test_opening_and_closing_derived_from_balance_column():
    # Arrange: first row 900.00 after a 100.00 debit means opening 1000.00
    lines = ("01/03/2026,A,100.00,,900.00", "02/03/2026,B,,500.00,1400.00")

    # Act
    statement = _parse(*lines)

    # Assert
    assert statement.opening_balance_minor == 100000
    assert statement.closing_balance_minor == 140000


def test_closing_balance_uses_last_stated_balance_even_when_it_differs_from_arithmetic():
    # Arrange: arithmetic would give 1400.00 but the statement states 9999.00
    lines = ("01/03/2026,A,100.00,,900.00", "02/03/2026,B,,500.00,9999.00")

    # Act
    statement = _parse(*lines)

    # Assert
    assert statement.closing_balance_minor == 999900


def test_opening_and_closing_derived_without_balance_column():
    # Arrange / Act
    statement = _parse("01/03/2026,A,100.00,", "02/03/2026,B,,500.00", header=SPLIT_HEADER)

    # Assert
    assert statement.opening_balance_minor == 0
    assert statement.closing_balance_minor == 40000
    assert all(row.stated_running_balance_minor is None for row in statement.rows)


def test_utf8_bom_is_ignored_before_header_matching():
    # Arrange
    content = b"\xef\xbb\xbf" + _csv("01/03/2026,Coffee,50.00,,950.00")

    # Act
    statement = GenericCsvParser().parse(content, FILENAME)

    # Assert
    assert statement.rows[0].raw_description == "Coffee"
    assert statement.layout_fingerprint == _parse("01/03/2026,Coffee,50.00,,950.00").layout_fingerprint


def test_blank_lines_are_skipped():
    # Arrange
    content = (
        f"\n{DEFAULT_HEADER}\n\n01/03/2026,A,1.00,,99.00\n\n,,,,\n02/03/2026,B,,1.00,100.00\n\n"
    ).encode()

    # Act
    statement = GenericCsvParser().parse(content, FILENAME)

    # Assert
    assert [row.raw_description for row in statement.rows] == ["A", "B"]


def test_missing_date_column_is_rejected():
    # Arrange
    content = _csv("Coffee,50.00,,", header="Description,Debit,Credit")

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_MISSING_COLUMN"):
        GenericCsvParser().parse(content, FILENAME)


def test_missing_description_column_is_rejected():
    # Arrange
    content = _csv("01/03/2026,50.00,", header="Date,Debit,Credit")

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_MISSING_COLUMN"):
        GenericCsvParser().parse(content, FILENAME)


def test_missing_amount_columns_are_rejected():
    # Arrange: debit present but no credit and no amount
    content = _csv("01/03/2026,Coffee,50.00", header="Date,Description,Debit")

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_MISSING_COLUMN"):
        GenericCsvParser().parse(content, FILENAME)


def test_header_only_file_is_rejected_as_no_rows():
    # Arrange
    content = _csv(header=SPLIT_HEADER)

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_NO_ROWS"):
        GenericCsvParser().parse(content, FILENAME)


def test_empty_file_is_rejected_as_no_header():
    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_NO_HEADER"):
        GenericCsvParser().parse(b"\n\n", FILENAME)


def test_non_utf8_content_is_rejected():
    # Arrange
    content = b"Date,Description,Debit,Credit\n01/03/2026,\xff,1.00,\n"

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_ENCODING"):
        GenericCsvParser().parse(content, FILENAME)


def test_row_with_debit_and_credit_is_rejected_naming_the_row():
    # Arrange
    content = _csv("01/03/2026,Ok,1.00,", "02/03/2026,Both,1.00,1.00", header=SPLIT_HEADER)

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_BAD_ROW_AMOUNT: data row 2"):
        GenericCsvParser().parse(content, FILENAME)


def test_row_with_neither_debit_nor_credit_is_rejected():
    # Arrange
    content = _csv("01/03/2026,Empty,,", header=SPLIT_HEADER)

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_BAD_ROW_AMOUNT: data row 1"):
        GenericCsvParser().parse(content, FILENAME)


def test_zero_signed_amount_is_rejected_as_neither_debit_nor_credit():
    # Arrange
    content = _csv("01/03/2026,Zero,0.00", header="Date,Description,Amount")

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_BAD_ROW_AMOUNT: data row 1"):
        GenericCsvParser().parse(content, FILENAME)


def test_negative_debit_column_value_is_rejected():
    # Arrange
    content = _csv("01/03/2026,Neg,-5.00,", header=SPLIT_HEADER)

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_BAD_AMOUNT: data row 1"):
        GenericCsvParser().parse(content, FILENAME)


def test_invalid_amount_text_is_rejected_naming_the_row():
    # Arrange
    content = _csv("01/03/2026,Bad,abc,", header=SPLIT_HEADER)

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_BAD_AMOUNT: data row 1"):
        GenericCsvParser().parse(content, FILENAME)


def test_too_many_data_rows_is_rejected():
    # Arrange
    rows = ["01/03/2026,Row,1.00," for _ in range(MAX_DATA_ROWS + 1)]
    content = _csv(*rows, header=SPLIT_HEADER)

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_TOO_MANY_ROWS"):
        GenericCsvParser().parse(content, FILENAME)


MAX_AMOUNT_TEXT = "10000000000000.00"  # MAX_ROW_AMOUNT_MINOR paise
ABOVE_MAX_AMOUNT_TEXT = "10000000000000.01"

LIMIT_CELL_LINES = {
    "debit": (SPLIT_HEADER, "01/03/2026,Big,{value},"),
    "credit": (SPLIT_HEADER, "01/03/2026,Big,,{value}"),
    "signed_amount": ("Date,Description,Amount", "01/03/2026,Big,{value}"),
    "balance": (DEFAULT_HEADER, "01/03/2026,Big,1.00,,{value}"),
}


def _limit_cell_content(cell: str, value: str) -> bytes:
    header, line = LIMIT_CELL_LINES[cell]
    return _csv(line.format(value=value), header=header)


@pytest.mark.parametrize("cell", list(LIMIT_CELL_LINES))
def test_amount_exactly_at_limit_is_accepted(cell):
    # Arrange
    content = _limit_cell_content(cell, MAX_AMOUNT_TEXT)

    # Act
    statement = GenericCsvParser().parse(content, FILENAME)

    # Assert
    row = statement.rows[0]
    if cell == "debit":
        assert row.debit_minor == MAX_ROW_AMOUNT_MINOR
    elif cell == "credit":
        assert row.credit_minor == MAX_ROW_AMOUNT_MINOR
    elif cell == "signed_amount":
        assert row.credit_minor == MAX_ROW_AMOUNT_MINOR
    else:
        assert row.stated_running_balance_minor == MAX_ROW_AMOUNT_MINOR


@pytest.mark.parametrize("cell", list(LIMIT_CELL_LINES))
def test_amount_one_paisa_above_limit_is_rejected_naming_the_row(cell):
    # Arrange
    content = _limit_cell_content(cell, ABOVE_MAX_AMOUNT_TEXT)

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_BAD_AMOUNT: data row 1"):
        GenericCsvParser().parse(content, FILENAME)


def test_negative_signed_amount_beyond_limit_is_rejected():
    # Arrange
    content = _limit_cell_content("signed_amount", "-" + ABOVE_MAX_AMOUNT_TEXT)

    # Act / Assert
    with pytest.raises(StatementParseError, match="CSV_BAD_AMOUNT: data row 1"):
        GenericCsvParser().parse(content, FILENAME)


def test_statement_date_range_spans_min_and_max_row_dates():
    # Arrange / Act
    statement = _parse("05/03/2026,A,1.00,", "01/03/2026,B,2.00,", header=SPLIT_HEADER)

    # Assert
    assert statement.statement_start_date == date(2026, 3, 1)
    assert statement.statement_end_date == date(2026, 3, 5)


def test_can_parse_true_for_csv_with_required_columns():
    # Arrange
    content = _csv("01/03/2026,Coffee,50.00,,950.00")

    # Act / Assert
    assert GenericCsvParser().can_parse(content, FILENAME) is True


def test_can_parse_true_for_uppercase_extension_and_bom():
    # Arrange
    content = b"\xef\xbb\xbf" + _csv("01/03/2026,Coffee,50.00,,950.00")

    # Act / Assert
    assert GenericCsvParser().can_parse(content, "STATEMENT.CSV") is True


def test_can_parse_false_for_non_csv_filename():
    # Arrange
    content = _csv("01/03/2026,Coffee,50.00,,950.00")

    # Act / Assert
    assert GenericCsvParser().can_parse(content, "statement.pdf") is False


def test_can_parse_false_when_required_column_is_missing():
    # Arrange
    content = _csv("Coffee,50.00", header="Description,Debit")

    # Act / Assert
    assert GenericCsvParser().can_parse(content, FILENAME) is False


def test_can_parse_false_for_non_utf8_content():
    # Arrange
    content = b"Date,Description,Debit,Credit\n01/03/2026,\xff,1.00,\n"

    # Act / Assert
    assert GenericCsvParser().can_parse(content, FILENAME) is False
