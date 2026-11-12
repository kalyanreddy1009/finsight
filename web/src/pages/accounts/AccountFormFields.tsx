import type { UserAccountSubtype } from "../../api/types";
import { Field } from "../../components/Field";
import { ACCOUNT_SUBTYPES, SUBTYPE_LABELS, isCardSubtype, isLiabilitySubtype, isUserAccountSubtype } from "./accountOptions";
import type { AccountFormErrors, AccountFormValues, AccountTextField } from "./accountForm";
import { SelectField } from "../../components/SelectField";

interface AccountFormFieldsProps {
  values: AccountFormValues;
  errors: AccountFormErrors;
  saving: boolean;
  onText: (key: AccountTextField, value: string) => void;
  onSubtype: (subtype: UserAccountSubtype) => void;
}

export function AccountFormFields({ values, errors, saving, onText, onSubtype }: AccountFormFieldsProps) {
  const isCard = isCardSubtype(values.subtype);
  const owedLabel = isLiabilitySubtype(values.subtype) ? "Amount Currently Owed" : "Opening balance";
  return (
    <>
      <Field
        id="account-name"
        label="Account name"
        autoComplete="off"
        maxLength={100}
        value={values.name}
        disabled={saving}
        error={errors.name}
        onChange={(event) => onText("name", event.target.value)}
      />
      <SelectField
        id="account-type"
        label="Account type"
        value={values.subtype}
        disabled={saving}
        onChange={(event) => {
          const next = event.target.value;
          if (isUserAccountSubtype(next)) {
            onSubtype(next);
          }
        }}
      >
        {ACCOUNT_SUBTYPES.map((subtype) => (
          <option key={subtype} value={subtype}>
            {SUBTYPE_LABELS[subtype]}
          </option>
        ))}
      </SelectField>
      <Field
        id="account-institution"
        label="Institution"
        hint="Optional, such as the bank or fund house"
        maxLength={100}
        value={values.institution}
        disabled={saving}
        error={errors.institution}
        onChange={(event) => onText("institution", event.target.value)}
      />
      {isCard ? (
        <>
          <Field
            id="account-credit-limit"
            label="Credit limit"
            hint="In rupees, optional"
            inputMode="decimal"
            value={values.creditLimit}
            disabled={saving}
            error={errors.creditLimit}
            onChange={(event) => onText("creditLimit", event.target.value)}
          />
          <Field
            id="account-billing-day"
            label="Billing day"
            hint="Day of the month, 1 to 31"
            inputMode="numeric"
            value={values.billingDay}
            disabled={saving}
            error={errors.billingDay}
            onChange={(event) => onText("billingDay", event.target.value)}
          />
          <Field
            id="account-due-day"
            label="Due day"
            hint="Day of the month, 1 to 31"
            inputMode="numeric"
            value={values.dueDay}
            disabled={saving}
            error={errors.dueDay}
            onChange={(event) => onText("dueDay", event.target.value)}
          />
        </>
      ) : null}
      <Field
        id="account-opening-balance"
        label={owedLabel}
        hint="In rupees. Leave blank if there is no balance yet."
        inputMode="decimal"
        value={values.openingBalance}
        disabled={saving}
        error={errors.openingBalance}
        onChange={(event) => onText("openingBalance", event.target.value)}
      />
      <Field
        id="account-opening-date"
        label="Opening date"
        type="date"
        hint="Required when a balance is entered"
        value={values.openingDate}
        disabled={saving}
        error={errors.openingDate}
        onChange={(event) => onText("openingDate", event.target.value)}
      />
    </>
  );
}
