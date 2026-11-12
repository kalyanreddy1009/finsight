import { useState } from "react";
import { Button } from "../components/Button";
import { useAuth } from "../auth/useAuth";
import { PlaceholderPage } from "./PlaceholderPage";

export function AssistantPage() {
  const { signOut } = useAuth();
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    setSigningOut(true);
    await signOut();
  }

  return (
    <PlaceholderPage
      title="Assistant"
      message="The assistant is not available yet. It will answer questions about your money here."
    >
      <div className="sign-out-row">
        <Button variant="plain" onClick={() => void handleSignOut()} disabled={signingOut}>
          {signingOut ? "Signing Out…" : "Sign Out"}
        </Button>
      </div>
    </PlaceholderPage>
  );
}
