import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getAiStatus, requestInsight, sendChat } from "../api/ai";
import { ApiError } from "../api/client";
import { getInsightsSummary } from "../api/insights";
import type { AiStatus, InsightsSummary } from "../api/types";
import { AssistantPage } from "./AssistantPage";
import { PRIVACY_LINE } from "./assistant/StatusCard";

vi.mock("../api/ai", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/ai")>()),
  getAiStatus: vi.fn(),
  sendChat: vi.fn(),
  requestInsight: vi.fn(),
}));
vi.mock("../api/insights", () => ({ getInsightsSummary: vi.fn() }));

const statusMock = vi.mocked(getAiStatus);
const chatMock = vi.mocked(sendChat);
const insightMock = vi.mocked(requestInsight);
const insightsMock = vi.mocked(getInsightsSummary);

const READY: AiStatus = {
  provider: "LOCAL_OLLAMA",
  reachable: true,
  model: "qwen3:4b",
  model_available: true,
  installed_models: ["qwen3:4b"],
  local_only: true,
};

const SUMMARY: InsightsSummary = {
  as_of: "2026-11-12",
  month: "2026-11",
  income_minor: 0,
  expense_minor: 0,
  net_minor: 0,
  previous_expense_minor: 0,
  categories: [],
  trend: [],
  highlights: [{ kind: "spend_up", severity: "warning", title: "Dining out is up 40%", detail: "More than last month." }],
};

function renderAssistant() {
  return render(<AssistantPage />);
}

async function readyPage() {
  statusMock.mockResolvedValue(READY);
  const view = renderAssistant();
  await screen.findByText("Running locally with");
  return view;
}

beforeEach(() => {
  vi.resetAllMocks();
  insightsMock.mockResolvedValue(SUMMARY);
});

describe("AssistantPage header and privacy", () => {
  it("shows the private eyebrow, the title and the privacy line in every state", async () => {
    statusMock.mockReturnValue(new Promise(() => undefined));
    renderAssistant();

    expect(screen.getByText("Private · On this device")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Assistant" })).toBeTruthy();
    expect(screen.getByText(PRIVACY_LINE)).toBeTruthy();
    expect(screen.getByText("Checking the local AI…")).toBeTruthy();
  });

});

describe("AssistantPage status states", () => {
  it("Ready: says it runs locally with the model and enables chat", async () => {
    await readyPage();

    expect(screen.getByText("Ready")).toBeTruthy();
    expect(screen.getByText("qwen3:4b")).toBeTruthy();
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).disabled).toBe(false);
    expect(screen.getByRole("button", { name: "Summarise My Month" })).toBeTruthy();
  });

  it("Model missing: shows the pull command, copies it and disables chat", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    statusMock.mockResolvedValue({ ...READY, model_available: false, installed_models: [] });
    renderAssistant();

    expect(await screen.findByText("Model missing")).toBeTruthy();
    expect(screen.getByText(/is not installed/)).toBeTruthy();
    expect(screen.getByText("ollama pull qwen3:4b")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Copy Command" }));

    expect(writeText).toHaveBeenCalledWith("ollama pull qwen3:4b");
    expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy();
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Summarise My Month" })).toBeNull();
  });

  it("Not running: gives two steps and Check Again re-checks the status", async () => {
    const user = userEvent.setup();
    statusMock.mockResolvedValueOnce({ ...READY, reachable: false, model_available: false, installed_models: [] });
    statusMock.mockResolvedValueOnce(READY);
    renderAssistant();

    expect(await screen.findByText("The local AI is not running")).toBeTruthy();
    expect(screen.getByText("ollama.com")).toBeTruthy();
    expect(screen.getByText("ollama pull qwen3:4b")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Check Again" }));

    expect(await screen.findByText("Running locally with")).toBeTruthy();
    expect(statusMock).toHaveBeenCalledTimes(2);
  });

  it("treats an AI_UNAVAILABLE error as not running", async () => {
    statusMock.mockRejectedValue(new ApiError(503, "AI_UNAVAILABLE", "The local AI is not running. Start Ollama, then try again."));
    renderAssistant();

    expect(await screen.findByText("The local AI is not running")).toBeTruthy();
  });

  it("still shows This Month highlights when the model is not available", async () => {
    statusMock.mockResolvedValue({ ...READY, reachable: false, model_available: false });
    renderAssistant();

    const card = (await screen.findByRole("heading", { name: "This Month" })).closest("section") as HTMLElement;
    expect(await within(card).findByText("Dining out is up 40%")).toBeTruthy();
    expect(within(card).getByText("Heads up")).toBeTruthy();
  });
});

describe("AssistantPage summary", () => {
  it("summarises the month, showing Summarising… while pending, then the result as text", async () => {
    const user = userEvent.setup();
    let resolve: (value: Awaited<ReturnType<typeof requestInsight>>) => void = () => undefined;
    insightMock.mockReturnValue(new Promise((done) => (resolve = done)));
    await readyPage();

    await user.click(screen.getByRole("button", { name: "Summarise My Month" }));
    const pending = screen.getByRole("button", { name: "Summarising…" }) as HTMLButtonElement;
    expect(pending.disabled).toBe(true);
    resolve({
      insight: {
        summary_headline: "Spending is steady <b>mostly</b>",
        key_observations: ["Rent is your biggest cost."],
        recommended_actions: ["Review dining out."],
        disclaimer: "This is not financial advice.",
      },
      model: "qwen3:4b",
      latency_ms: 1200,
    });

    expect(await screen.findByText("Spending is steady <b>mostly</b>")).toBeTruthy();
    expect(screen.getByText("Rent is your biggest cost.")).toBeTruthy();
    expect(screen.getByText("Review dining out.")).toBeTruthy();
    expect(screen.getByText("This is not financial advice.")).toBeTruthy();
    expect(document.querySelector(".ai-result b")).toBeNull();
    expect(screen.getByRole("button", { name: "Summarise My Month" })).toBeTruthy();
  });

  it("shows the server message when the summary fails", async () => {
    const user = userEvent.setup();
    insightMock.mockRejectedValue(new ApiError(504, "AI_TIMEOUT", "The local AI took too long to answer. Try again in a moment."));
    await readyPage();

    await user.click(screen.getByRole("button", { name: "Summarise My Month" }));

    expect((await screen.findByRole("alert")).textContent).toContain("took too long");
  });
});

describe("AssistantPage chat", () => {
  it("sends a suggested question and shows both sides with labels", async () => {
    const user = userEvent.setup();
    chatMock.mockResolvedValue({ answer: "About ₹4,000 a day.\nKeep an eye on bills.", model: "qwen3:4b", latency_ms: 800, facts: {} });
    await readyPage();

    await user.click(screen.getByRole("button", { name: "How much can I safely spend this week?" }));

    const log = screen.getByRole("log", { name: "Conversation" });
    expect(await within(log).findByText(/About ₹4,000 a day\./)).toBeTruthy();
    expect(within(log).getByText("You")).toBeTruthy();
    expect(within(log).getByText("Assistant")).toBeTruthy();
    expect(within(log).getByText("How much can I safely spend this week?")).toBeTruthy();
    expect(chatMock).toHaveBeenCalledWith("How much can I safely spend this week?", []);
  });

  it("sends on Enter, keeps Shift+Enter for a new line, and sends the earlier messages as history", async () => {
    const user = userEvent.setup();
    chatMock.mockResolvedValueOnce({ answer: "First answer", model: "m", latency_ms: 1, facts: {} });
    chatMock.mockResolvedValueOnce({ answer: "Second answer", model: "m", latency_ms: 1, facts: {} });
    await readyPage();
    const input = screen.getByLabelText("Your question") as HTMLTextAreaElement;

    await user.type(input, "Line one{Shift>}{Enter}{/Shift}Line two");
    expect(input.value).toBe("Line one\nLine two");
    await user.type(input, "{Enter}");
    expect(await screen.findByText("First answer")).toBeTruthy();
    expect(input.value).toBe("");
    await user.type(input, "And now?{Enter}");

    expect(await screen.findByText("Second answer")).toBeTruthy();
    expect(chatMock).toHaveBeenNthCalledWith(1, "Line one\nLine two", []);
    expect(chatMock).toHaveBeenNthCalledWith(2, "And now?", [
      { role: "user", content: "Line one\nLine two" },
      { role: "assistant", content: "First answer" },
    ]);
    expect(input.maxLength).toBe(500);
  });

  it("shows an inline error next to the question and retries it with Try Again", async () => {
    const user = userEvent.setup();
    chatMock.mockRejectedValueOnce(new ApiError(429, "AI_BUSY", "The AI is busy with another request. Wait a moment, then try again."));
    chatMock.mockResolvedValueOnce({ answer: "Here you go", model: "m", latency_ms: 1, facts: {} });
    await readyPage();

    await user.type(screen.getByLabelText("Your question"), "Which bills are due soon?{Enter}");

    const log = screen.getByRole("log", { name: "Conversation" });
    await within(log).findByText(/The AI is busy/);
    expect(within(log).queryByRole("alert")).toBeNull();
    await user.click(within(log).getByRole("button", { name: "Try Again" }));

    expect(await within(log).findByText("Here you go")).toBeTruthy();
    expect(within(log).queryByRole("alert")).toBeNull();
    expect(within(log).getAllByText("Which bills are due soon?")).toHaveLength(1);
    expect(chatMock).toHaveBeenCalledTimes(2);
    expect(chatMock).toHaveBeenLastCalledWith("Which bills are due soon?", []);
  });

  it("disables Send and shows Thinking… while a request is pending, then clears the conversation", async () => {
    const user = userEvent.setup();
    let resolve: (value: Awaited<ReturnType<typeof sendChat>>) => void = () => undefined;
    chatMock.mockReturnValue(new Promise((done) => (resolve = done)));
    await readyPage();

    await user.type(screen.getByLabelText("Your question"), "Am I on track?{Enter}");
    expect((screen.getByRole("button", { name: "Thinking…" }) as HTMLButtonElement).disabled).toBe(true);
    resolve({ answer: "Mostly.", model: "m", latency_ms: 1, facts: {} });
    expect(await screen.findByText("Mostly.")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Clear Conversation" }));

    await waitFor(() => expect(screen.queryByText("Mostly.")).toBeNull());
    expect(screen.queryByRole("button", { name: "Clear Conversation" })).toBeNull();
  });

  it("shows the server message and Try Again for an AI_TIMEOUT error", async () => {
    const user = userEvent.setup();
    chatMock.mockRejectedValueOnce(new ApiError(504, "AI_TIMEOUT", "The local AI took too long to answer. Try again in a moment."));
    chatMock.mockResolvedValueOnce({ answer: "Done", model: "m", latency_ms: 1, facts: {} });
    await readyPage();

    await user.type(screen.getByLabelText("Your question"), "Timed out?{Enter}");

    const log = screen.getByRole("log", { name: "Conversation" });
    expect(await within(log).findByText("The local AI took too long to answer. Try again in a moment.")).toBeTruthy();
    await user.click(within(log).getByRole("button", { name: "Try Again" }));
    expect(await within(log).findByText("Done")).toBeTruthy();
  });

  it("shows the server message and Try Again for an AI_MODEL_MISSING error, then checks the status again", async () => {
    const user = userEvent.setup();
    chatMock.mockRejectedValueOnce(new ApiError(503, "AI_MODEL_MISSING", "The model qwen3:4b is not installed."));
    await readyPage();
    statusMock.mockResolvedValueOnce({ ...READY, model_available: false, installed_models: [] });

    await user.type(screen.getByLabelText("Your question"), "Which model?{Enter}");

    const log = screen.getByRole("log", { name: "Conversation" });
    expect(await within(log).findByText("The model qwen3:4b is not installed.")).toBeTruthy();
    expect(within(log).getByRole("button", { name: "Try Again" })).toBeTruthy();
    expect(await screen.findByText("Model missing")).toBeTruthy();
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).disabled).toBe(true);
  });

  it("checks the AI status again when a chat fails with AI_UNAVAILABLE", async () => {
    const user = userEvent.setup();
    chatMock.mockRejectedValueOnce(new ApiError(503, "AI_UNAVAILABLE", "The local AI is not running. Start Ollama, then try again."));
    await readyPage();
    statusMock.mockResolvedValueOnce({ ...READY, reachable: false });

    await user.type(screen.getByLabelText("Your question"), "Still there?{Enter}");

    expect(await screen.findByText("The local AI is not running")).toBeTruthy();
    expect(statusMock).toHaveBeenCalledTimes(2);
  });

  it("moves focus back to the question box after a suggestion, Send and Try Again", async () => {
    const user = userEvent.setup();
    chatMock.mockRejectedValueOnce(new ApiError(429, "AI_BUSY", "The AI is busy with another request. Wait a moment, then try again."));
    chatMock.mockResolvedValue({ answer: "Noted", model: "m", latency_ms: 1, facts: {} });
    await readyPage();
    const input = screen.getByLabelText("Your question") as HTMLTextAreaElement;

    await user.click(screen.getByRole("button", { name: "Which bills are due soon?" }));
    expect(document.activeElement).toBe(input);

    const log = screen.getByRole("log", { name: "Conversation" });
    await user.click(await within(log).findByRole("button", { name: "Try Again" }));
    expect(document.activeElement).toBe(input);

    await user.type(input, "Am I on track?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(document.activeElement).toBe(input);
  });

  it("disables Summarise My Month while a chat request is pending", async () => {
    const user = userEvent.setup();
    chatMock.mockReturnValue(new Promise(() => undefined));
    await readyPage();

    await user.click(screen.getByRole("button", { name: "How much can I safely spend this week?" }));

    expect((screen.getByRole("button", { name: "Summarise My Month" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Clear Conversation" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("disables Send and the suggestion chips while a summary is pending", async () => {
    const user = userEvent.setup();
    insightMock.mockReturnValue(new Promise(() => undefined));
    await readyPage();
    await user.type(screen.getByLabelText("Your question"), "Hello");

    await user.click(screen.getByRole("button", { name: "Summarise My Month" }));

    expect((screen.getByRole("button", { name: "Send" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Which bills are due soon?" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("checks the AI status again when a summary fails with AI_UNAVAILABLE", async () => {
    const user = userEvent.setup();
    insightMock.mockRejectedValue(new ApiError(503, "AI_UNAVAILABLE", "The local AI is not running. Start Ollama, then try again."));
    await readyPage();
    statusMock.mockResolvedValueOnce({ ...READY, reachable: false });

    await user.click(screen.getByRole("button", { name: "Summarise My Month" }));

    expect(await screen.findByText("The local AI is not running")).toBeTruthy();
    expect(statusMock).toHaveBeenCalledTimes(2);
  });

  it("keeps the input disabled with a hint when the AI is not ready", async () => {
    statusMock.mockResolvedValue({ ...READY, reachable: false });
    renderAssistant();

    await screen.findByText("The local AI is not running");

    const input = screen.getByLabelText("Your question") as HTMLTextAreaElement;
    expect(input.disabled).toBe(true);
    expect(screen.getByText(/Chat turns on when the local AI is ready/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Which bills are due soon?" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
