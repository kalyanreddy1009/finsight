import { useId, useState, type FormEvent } from "react";
import { Button } from "../components/Button";
import { Field } from "../components/Field";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { AuthLayout } from "./AuthLayout";
import { signInErrorMessage } from "./authErrors";
import { useAuth } from "./useAuth";

export function SignInScreen() {
  useDocumentTitle("Sign In");
  const { signIn, signOutNotice } = useAuth();
  const passwordId = useId();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) {
      return;
    }
    if (password === "") {
      setError("Enter your password.");
      return;
    }
    setError(undefined);
    setSubmitting(true);
    try {
      await signIn(password);
    } catch (caught) {
      setError(signInErrorMessage(caught));
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Sign In to FinSight" intro="Enter your password to open FinSight in this browser.">
      {signOutNotice === null ? null : (
        <p className="field-error" role="status">
          {signOutNotice}
        </p>
      )}
      <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
        <Field
          id={passwordId}
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={error}
        />
        <Button variant="primary" type="submit" disabled={submitting}>
          {submitting ? "Signing In…" : "Sign In"}
        </Button>
      </form>
    </AuthLayout>
  );
}
