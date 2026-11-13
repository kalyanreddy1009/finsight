import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { sendChat } from "../../api/ai";
import { ApiError } from "../../api/client";
import { useChat } from "./useChat";

vi.mock("../../api/ai", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/ai")>()),
  sendChat: vi.fn(),
}));

const chatMock = vi.mocked(sendChat);

function reply(answer: string) {
  return { answer, model: "m", latency_ms: 1, facts: {} };
}

// Sends one question and waits until the request has finished.
async function ask(result: { current: ReturnType<typeof useChat> }, question: string) {
  act(() => {
    result.current.send(question);
  });
  await waitFor(() => expect(result.current.pending).toBe(false));
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("useChat history", () => {
  it("sends exactly the last 6 history entries, each cut to 2000 characters", async () => {
    const longAnswer = "a".repeat(2500);
    const { result } = renderHook(() => useChat(vi.fn()));
    chatMock.mockResolvedValueOnce(reply("a0"));
    await ask(result, "q0");
    chatMock.mockResolvedValueOnce(reply("a1"));
    await ask(result, "q1");
    chatMock.mockResolvedValueOnce(reply("a2"));
    await ask(result, "q2");
    chatMock.mockResolvedValueOnce(reply(longAnswer));
    await ask(result, "q3");

    chatMock.mockResolvedValueOnce(reply("a4"));
    await ask(result, "q4");

    expect(chatMock).toHaveBeenLastCalledWith("q4", [
      { role: "user", content: "q1" },
      { role: "assistant", content: "a1" },
      { role: "user", content: "q2" },
      { role: "assistant", content: "a2" },
      { role: "user", content: "q3" },
      { role: "assistant", content: "a".repeat(2000) },
    ]);
  });
});

describe("useChat replies", () => {
  it("shows the empty-reply error with Try Again and does not add a blank message", async () => {
    const { result } = renderHook(() => useChat(vi.fn()));
    chatMock.mockResolvedValueOnce(reply("   "));
    await ask(result, "Am I on track?");

    expect(result.current.entries.map((entry) => entry.role)).toEqual(["user"]);
    expect(result.current.failure?.message).toBe("The assistant returned an empty reply. Try again.");

    chatMock.mockResolvedValueOnce(reply("Mostly."));
    act(() => {
      result.current.retry();
    });
    await waitFor(() => expect(result.current.pending).toBe(false));

    expect(result.current.entries.map((entry) => entry.text)).toEqual(["Am I on track?", "Mostly."]);
    expect(chatMock).toHaveBeenLastCalledWith("Am I on track?", []);
  });

  it("calls onAiProblem for a status-related error code and not for other errors", async () => {
    const onAiProblem = vi.fn();
    const { result } = renderHook(() => useChat(onAiProblem));
    chatMock.mockRejectedValueOnce(new ApiError(503, "AI_MODEL_MISSING", "The model is not installed."));
    await ask(result, "First");
    expect(onAiProblem).toHaveBeenCalledTimes(1);

    chatMock.mockRejectedValueOnce(new ApiError(504, "AI_TIMEOUT", "The local AI took too long to answer."));
    await ask(result, "Second");
    expect(onAiProblem).toHaveBeenCalledTimes(1);
    expect(result.current.failure?.message).toBe("The local AI took too long to answer.");
  });
});
