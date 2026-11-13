import { request } from "./client";
import type { AiInsightReply, AiStatus, ChatMessage, ChatReply } from "./types";

// Local AI endpoints (/api/v1/ai). Calls can take up to two minutes; the server reports its own timeout.

export const MAX_QUESTION_LENGTH = 500;
export const MAX_HISTORY_MESSAGES = 6;

export async function getAiStatus(): Promise<AiStatus> {
  const { data } = await request<AiStatus>("GET", "/ai/status");
  return data;
}

export async function sendChat(question: string, history: readonly ChatMessage[] = []): Promise<ChatReply> {
  const body = { question, history: history.slice(-MAX_HISTORY_MESSAGES) };
  const { data } = await request<ChatReply>("POST", "/ai/chat", { body });
  return data;
}

export async function requestInsight(): Promise<AiInsightReply> {
  const { data } = await request<AiInsightReply>("POST", "/ai/insight");
  return data;
}
