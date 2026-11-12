import { ApiError } from "../../api/client";

const GENERIC_MESSAGE = "Something went wrong. Try again.";
const REUSED_KEY_MESSAGE = "This entry was already sent with different details. Close the form and add it again.";

// Server messages for VALIDATION_ERROR and NETWORK_ERROR are already user-facing.
export function describeError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return GENERIC_MESSAGE;
  }
  if (error.code === "IDEMPOTENCY_KEY_REUSED") {
    return REUSED_KEY_MESSAGE;
  }
  return error.message;
}

export function hasErrorCode(error: unknown, code: string): boolean {
  return error instanceof ApiError && error.code === code;
}
