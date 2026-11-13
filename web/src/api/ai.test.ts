import { beforeEach, describe, expect, it, vi } from "vitest";
import { getAiStatus, requestInsight, sendChat } from "./ai";
import { request } from "./client";
import type { ChatMessage } from "./types";

vi.mock("./client", () => ({ request: vi.fn() }));

const requestMock = vi.mocked(request);

describe("AI API", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("reads the status with a GET to /ai/status", async () => {
    const status = { reachable: true };
    requestMock.mockResolvedValue({ data: status, meta: null });

    expect(await getAiStatus()).toBe(status);
    expect(requestMock).toHaveBeenCalledWith("GET", "/ai/status");
  });

  it("posts the question with an empty history by default", async () => {
    requestMock.mockResolvedValue({ data: { answer: "Hi" }, meta: null });

    const reply = await sendChat("How am I doing?");

    expect(requestMock).toHaveBeenCalledWith("POST", "/ai/chat", { body: { question: "How am I doing?", history: [] } });
    expect(reply).toEqual({ answer: "Hi" });
  });

  it("sends only the last six history messages", async () => {
    requestMock.mockResolvedValue({ data: {}, meta: null });
    const history: ChatMessage[] = Array.from({ length: 8 }, (_, index) => ({
      role: index % 2 === 0 ? "user" : "assistant",
      content: `message ${index}`,
    }));

    await sendChat("Next?", history);

    const body = requestMock.mock.calls[0]?.[2]?.body as { history: ChatMessage[] };
    expect(body.history.map((message) => message.content)).toEqual([
      "message 2",
      "message 3",
      "message 4",
      "message 5",
      "message 6",
      "message 7",
    ]);
  });

  it("requests an insight with a POST and no body", async () => {
    const reply = { insight: { summary_headline: "ok" } };
    requestMock.mockResolvedValue({ data: reply, meta: null });

    expect(await requestInsight()).toBe(reply);
    expect(requestMock).toHaveBeenCalledWith("POST", "/ai/insight");
  });
});
