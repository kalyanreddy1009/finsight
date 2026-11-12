"""Statement upload, review, row review and commit. Thin handlers over app.ingestion.pipeline."""

import os
import re
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Form, Query, Response, UploadFile

from app.api.deps import Conn, DeviceId, IdempotencyKey, SettingsDep
from app.api.envelope import ok
from app.api.errors import ApiError, not_found
from app.api.v1.schemas import Body, Id
from app.core.config import Settings
from app.ingestion import pipeline, statement_commit
from app.ingestion.base_parser import StatementParseError
from app.ingestion.csv_parser import GenericCsvParser
from app.ingestion.document_store import DocumentStore
from app.ingestion.drift_guard import LayoutDriftError, verify_layout

router = APIRouter(prefix="/statements", tags=["statements"])

MAX_UPLOAD_BYTES = pipeline.MAX_FILE_BYTES
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_NAME_CHARS = 200
MAX_SUFFIX_CHARS = 10
UploadKind = Literal["BANK_PDF", "CARD_PDF", "CSV", "CAS_PDF"]
RowStatus = Literal["USER_APPROVED", "REJECTED", "PENDING_REVIEW"]
ProcessingStatus = Literal["UPLOADED", "PARSING", "REVIEW_REQUIRED", "APPROVED", "FAILED"]
_CODE_RE = re.compile(r"[A-Z][A-Z0-9_]*")
_REJECTION_STATUS = {"FILE_TOO_LARGE": 413, "ACCOUNT_NOT_FOUND": 404}
_LIST_SQL = (
    "SELECT id, account_id, statement_kind, original_filename, statement_start_date, statement_end_date, "
    "opening_balance_minor, closing_balance_minor, reconciliation_diff_minor, processing_status, "
    "uploaded_at, approved_at FROM statements "
    "WHERE (? IS NULL OR account_id = ?) AND (? IS NULL OR processing_status = ?) "
    "ORDER BY uploaded_at DESC, id DESC LIMIT ?"
)


class RowUpdateIn(Body):
    row_status: RowStatus | None = None
    suggested_category_id: Id | None = None


def _list_statements(
    conn: sqlite3.Connection, account_id: str | None, processing_status: str | None, limit: int
) -> list[dict[str, Any]]:
    params = (account_id, account_id, processing_status, processing_status, limit)
    return [dict(row) for row in conn.execute(_LIST_SQL, params).fetchall()]


def _document_store(settings: Settings) -> DocumentStore:
    try:
        master_key = bytes.fromhex(settings.master_key.get_secret_value()) if settings.master_key else b""
        return DocumentStore(Path(settings.docs_dir), master_key)
    except ValueError:
        raise ApiError(503, "STORAGE_NOT_CONFIGURED", "Statement storage is not configured.") from None


def _safe_file_name(raw: str | None) -> str:
    """Keeps only the base name of the client file name, truncated to MAX_NAME_CHARS."""
    name = re.split(r"[\\/]", raw or "")[-1].strip()
    if not name:
        raise ApiError(422, "VALIDATION_ERROR", "The upload needs a file name.")
    if len(name) <= MAX_NAME_CHARS:
        return name
    stem, suffix = os.path.splitext(name)
    if len(suffix) > MAX_SUFFIX_CHARS:
        suffix = ""
    return stem[: MAX_NAME_CHARS - len(suffix)] + suffix


def _coded_error(exc: Exception) -> ApiError:
    """Maps an error whose message starts with an UPPER_SNAKE code to an ApiError."""
    text = str(exc)
    code = text.partition(":")[0]
    if _CODE_RE.fullmatch(code) is None:
        code = "VALIDATION_ERROR"
    return ApiError(_REJECTION_STATUS.get(code, 422), code, text)


def _ingest(
    conn: sqlite3.Connection,
    store: DocumentStore,
    account_id: str,
    filename: str,
    content: bytes,
    kind: str,
) -> pipeline.IngestResult:
    try:
        return pipeline.ingest_statement(
            conn,
            account_id=account_id,
            filename=filename,
            content=content,
            statement_kind=kind,
            parsers=[GenericCsvParser()],
            document_store=store,
            verify_layout=verify_layout,
        )
    except pipeline.DuplicateStatementError as duplicate:
        raise ApiError(
            409,
            "DUPLICATE_STATEMENT",
            "This statement was already imported.",
            meta={"statement_id": duplicate.statement_id},
        ) from None
    except (pipeline.StatementRejectedError, StatementParseError, LayoutDriftError) as rejected:
        raise _coded_error(rejected) from None


@router.get("")
async def list_statements(
    conn: Conn,
    _: DeviceId,
    account_id: Annotated[str | None, Query(max_length=64)] = None,
    processing_status: Annotated[ProcessingStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> dict:
    return ok(_list_statements(conn, account_id, processing_status, limit))


@router.post("/upload", status_code=201)
async def upload_statement(
    file: UploadFile,
    account_id: Annotated[str, Form(max_length=64)],
    statement_kind: Annotated[UploadKind, Form()],
    conn: Conn,
    settings: SettingsDep,
    _: DeviceId,
) -> dict:
    store = _document_store(settings)
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "FILE_TOO_LARGE", "Statement files are limited to 25 MB.")
    result = _ingest(conn, store, account_id, _safe_file_name(file.filename), content, statement_kind)
    return ok(asdict(result))


@router.get("/{statement_id}/review")
async def review_statement(statement_id: str, conn: Conn, _: DeviceId) -> dict:
    try:
        review = pipeline.get_review(conn, statement_id)
    except pipeline.StatementNotFoundError:
        raise not_found("Statement") from None
    return ok(
        {
            "statement": review.statement,
            "rows": list(review.rows),
            "import_errors": list(review.import_errors),
        }
    )


@router.patch("/rows/{row_id}")
async def update_statement_row(row_id: str, body: RowUpdateIn, conn: Conn, _: DeviceId) -> dict:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    try:
        pipeline.update_row(conn, row_id, **changes)
    except pipeline.RowNotFoundError:
        raise not_found("Statement row") from None
    except pipeline.InvalidRowUpdateError as exc:
        raise ApiError(422, "VALIDATION_ERROR", str(exc)) from None
    return ok({"id": row_id, **changes})


@router.post("/{statement_id}/commit", status_code=201)
async def commit_statement_endpoint(
    statement_id: str, conn: Conn, response: Response, key: IdempotencyKey, _: DeviceId
) -> dict:
    try:
        result = statement_commit.commit_statement(conn, statement_id, idempotency_key=key)
    except pipeline.StatementNotFoundError:
        raise not_found("Statement") from None
    except statement_commit.StatementNotReconciledError as exc:
        raise ApiError(409, "STATEMENT_NOT_RECONCILED", str(exc)) from None
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", str(exc)) from None
    if result.already_committed:
        response.status_code = 200
    return ok(asdict(result))
