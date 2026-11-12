import { useId, useState, type FormEvent } from "react";
import { DEFAULT_DEVICE_NAME } from "../api/auth";
import { Button } from "../components/Button";
import { Field } from "../components/Field";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { AuthLayout } from "./AuthLayout";
import { SETUP_CODE_INCORRECT, isInvalidSetupCode, setupErrorMessage } from "./authErrors";
import {
  MIN_PASSWORD_LENGTH,
  confirmProblem,
  deviceNameProblem,
  hasSetupErrors,
  passwordProblem,
  setupCodeProblem,
  validateSetup,
  type SetupErrors,
} from "./setupValidation";
import { useAuth } from "./useAuth";

export function SetupScreen() {
  useDocumentTitle("Set Up");
  const { setUp } = useAuth();
  const ids = { password: useId(), confirm: useId(), deviceName: useId(), setupCode: useId() };
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [deviceName, setDeviceName] = useState(DEFAULT_DEVICE_NAME);
  const [setupCode, setSetupCode] = useState("");
  const [errors, setErrors] = useState<SetupErrors>({});
  const [formError, setFormError] = useState<string | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) {
      return;
    }
    const nextErrors = validateSetup({ password, confirm, deviceName, setupCode });
    setErrors(nextErrors);
    if (hasSetupErrors(nextErrors)) {
      return;
    }
    setFormError(undefined);
    setSubmitting(true);
    try {
      await setUp(password, deviceName.trim(), setupCode.trim());
    } catch (caught) {
      if (isInvalidSetupCode(caught)) {
        setErrors((prev) => ({ ...prev, setupCode: SETUP_CODE_INCORRECT }));
      } else {
        setFormError(setupErrorMessage(caught));
      }
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Set Up FinSight"
      intro="Choose the password you will use to open FinSight. You can sign in again from any browser later."
    >
      <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
        <Field
          id={ids.password}
          label="Password"
          type="password"
          autoComplete="new-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          onBlur={() => setErrors((prev) => ({ ...prev, password: passwordProblem(password) }))}
          error={errors.password}
        />
        <Field
          id={ids.confirm}
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          onBlur={() => setErrors((prev) => ({ ...prev, confirm: confirmProblem(password, confirm) }))}
          error={errors.confirm}
        />
        <Field
          id={ids.deviceName}
          label="Device name"
          type="text"
          autoComplete="off"
          hint="Shown in your list of signed-in devices."
          value={deviceName}
          onChange={(event) => setDeviceName(event.target.value)}
          onBlur={() => setErrors((prev) => ({ ...prev, deviceName: deviceNameProblem(deviceName) }))}
          error={errors.deviceName}
        />
        <Field
          id={ids.setupCode}
          label="Setup Code"
          type="text"
          autoComplete="off"
          hint="Shown in the server configuration as FINSIGHT_SETUP_TOKEN"
          value={setupCode}
          onChange={(event) => setSetupCode(event.target.value)}
          onBlur={() => setErrors((prev) => ({ ...prev, setupCode: setupCodeProblem(setupCode) }))}
          error={errors.setupCode}
        />
        {formError ? (
          <p className="field-error" role="alert">
            {formError}
          </p>
        ) : null}
        <Button variant="primary" type="submit" disabled={submitting}>
          {submitting ? "Setting Up…" : "Finish Setup"}
        </Button>
      </form>
    </AuthLayout>
  );
}
