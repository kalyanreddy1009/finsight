import { describe, expect, it } from "vitest";
import { EMPTY_ACCOUNT_FORM, validateAccountForm, type AccountFormValues } from "./accountForm";

const DAY_ERROR = "Enter a day from 1 to 31.";

function bankForm(overrides: Partial<AccountFormValues> = {}): AccountFormValues {
  return { ...EMPTY_ACCOUNT_FORM, name: "HDFC Savings", ...overrides };
}

function cardForm(overrides: Partial<AccountFormValues> = {}): AccountFormValues {
  return bankForm({ subtype: "CREDIT_CARD", ...overrides });
}

describe("validateAccountForm", () => {
  describe("name and institution", () => {
    it("requires a name once surrounding spaces are removed", () => {
      const result = validateAccountForm(bankForm({ name: "   " }));

      expect(result.errors.name).toBe("Enter a name for this account.");
      expect(result.body).toBeNull();
    });

    it("rejects a name longer than 100 characters and accepts exactly 100", () => {
      expect(validateAccountForm(bankForm({ name: "a".repeat(101) })).errors.name).toBe("Use 100 characters or fewer.");
      expect(validateAccountForm(bankForm({ name: "a".repeat(100) })).errors.name).toBeUndefined();
    });

    it("rejects an institution longer than 100 characters", () => {
      const result = validateAccountForm(bankForm({ institution: "b".repeat(101) }));

      expect(result.errors.institution).toBe("Use 100 characters or fewer.");
      expect(result.body).toBeNull();
    });

    it("trims the name and institution and omits a blank institution from the body", () => {
      const named = validateAccountForm(bankForm({ name: "  Wallet  ", institution: "  HDFC  " }));
      const blank = validateAccountForm(bankForm({ institution: "   " }));

      expect(named.body?.name).toBe("Wallet");
      expect(named.body?.institution).toBe("HDFC");
      expect(blank.body).not.toHaveProperty("institution");
    });
  });

  describe("card fields", () => {
    it("ignores card-only fields for a non-card account", () => {
      const result = validateAccountForm(
        bankForm({ creditLimit: "abc", billingDay: "99", dueDay: "0" }),
      );

      expect(result.errors).toEqual({});
      expect(result.body).not.toHaveProperty("credit_limit_minor");
      expect(result.body).not.toHaveProperty("billing_day");
      expect(result.body).not.toHaveProperty("due_day");
    });

    it.each(["abc", "0", "-500"])("rejects a credit limit of %j", (creditLimit) => {
      const result = validateAccountForm(cardForm({ creditLimit }));

      expect(result.errors.creditLimit).toBe("Enter the limit in rupees, such as 50000.");
      expect(result.body).toBeNull();
    });

    it.each(["0", "32", "x1", "123"])("rejects billing day %j", (billingDay) => {
      expect(validateAccountForm(cardForm({ billingDay })).errors.billingDay).toBe(DAY_ERROR);
    });

    it.each(["0", "40", "d"])("rejects due day %j", (dueDay) => {
      expect(validateAccountForm(cardForm({ dueDay })).errors.dueDay).toBe(DAY_ERROR);
    });

    it("sends the card limit in paise and the days as numbers", () => {
      const result = validateAccountForm(
        cardForm({ creditLimit: " 50,000 ", billingDay: "05", dueDay: "25" }),
      );

      expect(result.errors).toEqual({});
      expect(result.body).toMatchObject({
        account_subtype: "CREDIT_CARD",
        credit_limit_minor: 5000000,
        billing_day: 5,
        due_day: 25,
      });
    });

    it("omits blank card fields from the body", () => {
      const result = validateAccountForm(cardForm({ creditLimit: "  ", billingDay: "", dueDay: " " }));

      expect(result.body).not.toHaveProperty("credit_limit_minor");
      expect(result.body).not.toHaveProperty("billing_day");
      expect(result.body).not.toHaveProperty("due_day");
    });
  });

  describe("opening balance", () => {
    it.each(["0", "-5", "abc"])("rejects an opening balance of %j", (openingBalance) => {
      const result = validateAccountForm(bankForm({ openingBalance, openingDate: "2026-01-01" }));

      expect(result.errors.openingBalance).toBe("Enter an amount above zero in rupees, or leave this blank.");
      expect(result.body).toBeNull();
    });

    it("requires the date an opening balance is as of", () => {
      const result = validateAccountForm(bankForm({ openingBalance: "1000", openingDate: "" }));

      expect(result.errors.openingDate).toBe("Enter the date this balance is as of.");
      expect(result.body).toBeNull();
    });

    it("rejects a malformed opening date", () => {
      const result = validateAccountForm(bankForm({ openingBalance: "1000", openingDate: "01/01/2026" }));

      expect(result.errors.openingDate).toBe("Enter the date this balance is as of.");
    });

    it("sends the opening balance in paise with its date", () => {
      const result = validateAccountForm(bankForm({ openingBalance: "1000.50", openingDate: "2026-01-01" }));

      expect(result.errors).toEqual({});
      expect(result.body).toMatchObject({ opening_balance_minor: 100050, opening_date: "2026-01-01" });
    });

    it("omits the opening balance and date when the balance is blank, even with a date", () => {
      const result = validateAccountForm(bankForm({ openingBalance: "  ", openingDate: "garbage" }));

      expect(result.errors).toEqual({});
      expect(result.body).not.toHaveProperty("opening_balance_minor");
      expect(result.body).not.toHaveProperty("opening_date");
    });
  });

  it("reports every invalid field at once and returns no body", () => {
    const result = validateAccountForm(
      cardForm({ name: "", creditLimit: "0", billingDay: "0", dueDay: "40", openingBalance: "0" }),
    );

    expect(Object.keys(result.errors).sort()).toEqual(
      ["billingDay", "creditLimit", "dueDay", "name", "openingBalance"].sort(),
    );
    expect(result.body).toBeNull();
  });
});
