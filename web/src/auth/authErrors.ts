import { ApiError } from "../api/client";

// Plain-language messages for auth failures. Codes come from backend/app/api/v1/auth.py.
const SIGN_IN_MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: "That password is not right. Check it and try again.",
  TOO_MANY_ATTEMPTS: "Too many failed attempts. Wait a few minutes, then try again.",
  NETWORK_ERROR: "FinSight cannot be reached. Check your connection and try again.",
};

const SIGN_IN_FALLBACK = "Sign in did not work. Try again.";
const SETUP_FALLBACK = "Setup did not finish. Check the details and try again.";
export const SETUP_CODE_INCORRECT = "That setup code is not correct.";
const SETUP_CODE_NOT_CONFIGURED =
  "The server has no setup code configured. Set FINSIGHT_SETUP_TOKEN and restart it.";

// INVALID_SETUP_TOKEN is shown beside the Setup Code field, not as a form-level message.
export function isInvalidSetupCode(error: unknown): boolean {
  return error instanceof ApiError && error.code === "INVALID_SETUP_TOKEN";
}

export function signInErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return SIGN_IN_MESSAGES[error.code] ?? SIGN_IN_FALLBACK;
  }
  return SIGN_IN_FALLBACK;
}

export function setupErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === "NETWORK_ERROR") {
    return SIGN_IN_MESSAGES.NETWORK_ERROR ?? SETUP_FALLBACK;
  }
  if (error instanceof ApiError && error.code === "SETUP_TOKEN_NOT_CONFIGURED") {
    return SETUP_CODE_NOT_CONFIGURED;
  }
  return SETUP_FALLBACK;
}
