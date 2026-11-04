import type { MessageSeverity, ValidationMessage } from "./types";

const ORDER: Record<MessageSeverity, number> = {
  error: 0,
  warning: 1,
  info: 2,
};

/** Errors first, then warnings, then notes; keeps the server's order within
 *  each. The severity is spelled out, never colour alone. */
export function sortMessages(
  messages: ValidationMessage[],
): ValidationMessage[] {
  return messages
    .map((m, i) => ({ m, i }))
    .sort((x, y) => ORDER[x.m.severity] - ORDER[y.m.severity] || x.i - y.i)
    .map(({ m }) => m);
}
