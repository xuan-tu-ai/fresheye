// Turns the stored message log of an inspection into what a person should see.

import type { MessageOut } from "../api/types";

/** The request the backend stores when the app asks for an explanation (backend/app/agent/prompts.py). */
const EXPLAIN_REQUEST = "Hãy giải thích kết quả kiểm tra này cho tôi.";

function isSpoken(message: MessageOut): boolean {
  // Tool calls and tool results are the agent's working notes, not conversation.
  return message.role !== "tool" && message.tool_name === null && message.content.trim() !== "";
}

/** Messages to show in the conversation: what the user typed and what the assistant said. */
export function visibleMessages(messages: MessageOut[]): MessageOut[] {
  return messages.filter((m) => isSpoken(m) && !(m.role === "user" && m.content === EXPLAIN_REQUEST));
}

/** The assistant's latest explanation of the result, or null if none has been written yet. */
export function storedExplanation(messages: MessageOut[]): string | null {
  const asked = messages
    .map((m) => m.role === "user" && m.content === EXPLAIN_REQUEST)
    .lastIndexOf(true);
  if (asked === -1) return null;
  const answer = messages.slice(asked + 1).find((m) => m.role === "assistant" && isSpoken(m));
  return answer?.content ?? null;
}
