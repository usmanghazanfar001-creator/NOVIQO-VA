export type Status = "idle" | "listening" | "thinking" | "speaking" | "error";
export interface Msg { role: "user" | "assistant"; content: string; via: "voice" | "text"; }
export interface User { id: string; email: string; name: string; }
export interface Settings { memory_enabled: boolean; auto_speak: boolean; speech_rate: number; voice: string | null; theme: "dark" | "light" | "system"; }
export const DEFAULT_SETTINGS: Settings = { memory_enabled: true, auto_speak: true, speech_rate: 1, voice: null, theme: "dark" };
export interface ConvSummary { id: string; title: string; updated_at: string; via: "voice" | "text"; }
export interface Memory { id: number; text: string; }
export interface Reminder { id: number; text: string; due_at: string; }
