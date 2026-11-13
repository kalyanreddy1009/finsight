import { useCallback, useEffect, useRef, useState } from "react";
import { MAX_HISTORY_MESSAGES, sendChat } from "../../api/ai";
import { ApiError } from "../../api/client";
import type { ChatMessage } from "../../api/types";
import { isAiStatusProblem } from "./useAiStatus";

export interface ChatEntry {
  id: number;
  role: ChatMessage["role"];
  text: string;
}

export interface ChatFailure {
  question: string;
  history: ChatMessage[];
  message: string;
}

const FALLBACK_MESSAGE = "The assistant could not answer. Try again.";
const EMPTY_REPLY_MESSAGE = "The assistant returned an empty reply. Try again.";
// The server accepts at most 2000 characters per history message.
const MAX_HISTORY_CHARS = 2000;

// Blank entries are left out before the last few are kept, so the history is never padded with nothing.
function historyOf(entries: readonly ChatEntry[]): ChatMessage[] {
  return entries
    .filter((entry) => entry.text.trim() !== "")
    .slice(-MAX_HISTORY_MESSAGES)
    .map((entry) => ({ role: entry.role, content: entry.text.slice(0, MAX_HISTORY_CHARS) }));
}

export interface ChatApi {
  entries: readonly ChatEntry[];
  pending: boolean;
  failure: ChatFailure | null;
  send: (question: string) => boolean;
  retry: () => void;
  clear: () => void;
}

// Conversation state lives here only. Nothing is stored, and one request runs at a time.
// onAiProblem is called when the error means the local AI status has changed.
export function useChat(onAiProblem: () => void): ChatApi {
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ChatFailure | null>(null);
  const busy = useRef(false);
  const mounted = useRef(true);
  const nextId = useRef(1);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const addEntry = useCallback((role: ChatEntry["role"], text: string) => {
    const entry: ChatEntry = { id: nextId.current, role, text };
    nextId.current += 1;
    setEntries((previous) => [...previous, entry]);
  }, []);

  const run = useCallback(
    async (question: string, history: ChatMessage[]) => {
      busy.current = true;
      setPending(true);
      setFailure(null);
      try {
        const reply = await sendChat(question, history);
        if (mounted.current) {
          if (reply.answer.trim() === "") {
            setFailure({ question, history, message: EMPTY_REPLY_MESSAGE });
          } else {
            addEntry("assistant", reply.answer);
          }
        }
      } catch (error) {
        if (mounted.current) {
          setFailure({ question, history, message: error instanceof ApiError ? error.message : FALLBACK_MESSAGE });
          if (isAiStatusProblem(error)) {
            onAiProblem();
          }
        }
      } finally {
        busy.current = false;
        if (mounted.current) {
          setPending(false);
        }
      }
    },
    [addEntry, onAiProblem],
  );

  const send = (question: string): boolean => {
    const trimmed = question.trim();
    if (trimmed === "" || busy.current) {
      return false;
    }
    const history = historyOf(entries);
    addEntry("user", trimmed);
    void run(trimmed, history);
    return true;
  };

  const retry = () => {
    if (failure !== null && !busy.current) {
      void run(failure.question, failure.history);
    }
  };

  const clear = () => {
    if (busy.current) {
      return;
    }
    setEntries([]);
    setFailure(null);
  };

  return { entries, pending, failure, send, retry, clear };
}
