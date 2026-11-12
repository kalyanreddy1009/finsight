import { ApiError } from "../../api/client";
import type { ApiMeta } from "../../api/types";
import { messageFor } from "./format";

export interface UploadFailure {
  message: string;
  statementId: string | null;
}

const DUPLICATE_MESSAGE = "This file was already uploaded.";

const KNOWN_MESSAGES: Readonly<Record<string, string>> = {
  FILE_TOO_LARGE: "Statement files are limited to 25 MB. Choose a smaller file.",
  LAYOUT_DRIFT: "This statement's layout differs from the last one for this account, so it was not imported.",
  STORAGE_NOT_CONFIGURED: "The server's document storage is not configured (FINSIGHT_MASTER_KEY).",
};

function statementIdFrom(meta: ApiMeta): string | null {
  const id = meta?.statement_id;
  return typeof id === "string" ? id : null;
}

// Maps an upload error to user text. CSV_* and other server codes show the server's message.
export function uploadFailure(error: unknown): UploadFailure {
  if (!(error instanceof ApiError)) {
    return { message: messageFor(error), statementId: null };
  }
  if (error.code === "DUPLICATE_STATEMENT") {
    return { message: DUPLICATE_MESSAGE, statementId: statementIdFrom(error.meta) };
  }
  return { message: KNOWN_MESSAGES[error.code] ?? error.message, statementId: null };
}
