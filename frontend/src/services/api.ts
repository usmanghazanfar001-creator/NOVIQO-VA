import type { ConvSummary, Memory, Msg, Reminder, Settings, User } from "../types";
export type Action = { type: "timer"; seconds: number; label: string } | { type: "open_url"; url: string };
export interface Pending { token: string; summary: string; tool: string; voice_ok: boolean; }
export class ApiError extends Error { constructor(m: string, public status: number) { super(m); } }

async function req<T>(method: string, path: string, body?: object): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, { method, headers: body ? { "Content-Type": "application/json" } : undefined, body: body && JSON.stringify(body) });
  } catch { throw new Error("Network error. Check your connection."); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(d.error ?? "Request failed.", r.status);
  return d as T;
}
const tz = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

// auth
export const me = () => req<User>("GET", "/api/auth/me");
export const login = (email: string, password: string) => req<User>("POST", "/api/auth/login", { email, password });
export const signup = (email: string, password: string, name: string) => req<User>("POST", "/api/auth/signup", { email, password, name });
export const logout = () => req("POST", "/api/auth/logout");
export const forgot = (email: string) => req("POST", "/api/auth/forgot", { email });
export const reset = (token: string, password: string) => req("POST", "/api/auth/reset", { token, password });
export const updateName = (name: string) => req<User>("PATCH", "/api/auth/me", { name });
// chat
export const chat = (message: string, conversation_id: string | null, via: Msg["via"]) =>
  req<{ conversation_id: string; reply: string; actions: Action[]; pending: Pending[] }>("POST", "/api/chat", { message, conversation_id, via, tz: tz() });
export const confirmAction = (token: string) => req<{ reply: string; actions: Action[] }>("POST", "/api/confirm", { token, tz: tz() });
export interface StreamResult { conversation_id: string; reply: string; actions: Action[]; pending: Pending[]; }
/** Like chat(), but calls on.delta with text as it is written. on.reset means "discard what you showed so far" (a tool round began). */
export async function chatStream(message: string, conversation_id: string | null, via: Msg["via"], on: { delta(t: string): void; reset(): void }): Promise<StreamResult> {
  let r: Response;
  try {
    r = await fetch("/api/chat/stream", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation_id, via, tz }) });
  } catch { throw new Error("Network error. Check your connection."); }
  if (!r.ok || !r.body) { const d = await r.json().catch(() => ({})); throw new ApiError(d.error ?? "Request failed.", r.status); }
  const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "";
  for (;;) {
    const { done, value } = await reader.read(); if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i); buf = buf.slice(i + 2);
      const name = /^event: (\w+)/m.exec(block)?.[1], data = JSON.parse(/^data: (.*)$/m.exec(block)?.[1] ?? "{}");
      if (name === "delta") on.delta(data.text); else if (name === "reset") on.reset();
      else if (name === "error") throw new Error(data.error); else if (name === "done") return data;
    }
  }
  throw new Error("The connection closed before the reply finished.");
}
// history
export const listConvs = (q: string) => req<ConvSummary[]>("GET", `/api/conversations?q=${encodeURIComponent(q)}`);
export const getConv = (id: string) => req<{ messages: Msg[] }>("GET", `/api/conversations/${id}`);
export const renameConv = (id: string, title: string) => req("PATCH", `/api/conversations/${id}`, { title });
export const deleteConv = (id: string) => req("DELETE", `/api/conversations/${id}`);
// memory, settings, privacy
export const listMemories = () => req<Memory[]>("GET", "/api/memories");
export const deleteMemory = (id: number) => req("DELETE", `/api/memories/${id}`);
export const clearMemories = () => req("DELETE", "/api/memories");
export const getSettings = () => req<Settings>("GET", "/api/settings");
export const putSettings = (s: Settings) => req<Settings>("PUT", "/api/settings", s);
export const deleteAllData = () => req("DELETE", "/api/me/data");
export const deleteAccount = (password: string) => req("POST", "/api/me/delete", { password });
// reminders
export const listReminders = () => req<Reminder[]>("GET", "/api/reminders");
export const dueReminders = () => req<Reminder[]>("GET", "/api/reminders/due");
export const cancelReminder = (id: number) => req("DELETE", `/api/reminders/${id}`);
// calendar
export const calendarStatus = () => req<{ configured: boolean; connected: boolean }>("GET", "/api/calendar/status");
export const disconnectCalendar = () => req("DELETE", "/api/calendar");
