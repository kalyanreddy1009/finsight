import { useCallback, useEffect, useState } from "react";
import { getAiStatus } from "../../api/ai";
import { ApiError } from "../../api/client";
import type { AiStatus } from "../../api/types";

export type AiState =
  | { kind: "loading" }
  | { kind: "ready"; model: string }
  | { kind: "missing"; model: string }
  // model is null when the server could not be reached at all, so the name is unknown.
  | { kind: "down"; model: string | null }
  | { kind: "error"; message: string };

const FALLBACK_MESSAGE = "Could not check the local AI. Try again.";
// Chat and summary errors with these codes mean the status card is out of date, so it is checked again.
const STATUS_PROBLEM_CODES: ReadonlySet<string> = new Set(["AI_UNAVAILABLE", "AI_MODEL_MISSING", "AI_NOT_LOCAL"]);

export function isAiStatusProblem(error: unknown): boolean {
  return error instanceof ApiError && STATUS_PROBLEM_CODES.has(error.code);
}

function stateFromStatus(status: AiStatus): AiState {
  if (!status.reachable) {
    return { kind: "down", model: status.model };
  }
  return status.model_available ? { kind: "ready", model: status.model } : { kind: "missing", model: status.model };
}

function stateFromError(error: unknown): AiState {
  if (error instanceof ApiError && error.code === "AI_UNAVAILABLE") {
    return { kind: "down", model: null };
  }
  return { kind: "error", message: error instanceof ApiError ? error.message : FALLBACK_MESSAGE };
}

// Checks the local AI once on mount and again whenever check() is called.
export function useAiStatus(): { state: AiState; check: () => void } {
  const [state, setState] = useState<AiState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    getAiStatus().then(
      (status) => {
        if (active) {
          setState(stateFromStatus(status));
        }
      },
      (error: unknown) => {
        if (active) {
          setState(stateFromError(error));
        }
      },
    );
    return () => {
      active = false;
    };
  }, [attempt]);

  const check = useCallback(() => {
    setState({ kind: "loading" });
    setAttempt((count) => count + 1);
  }, []);

  return { state, check };
}
