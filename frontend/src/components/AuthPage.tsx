import { useState, type FormEvent } from "react";
import * as api from "../services/api";
import type { User } from "../types";

type Mode = "login" | "signup" | "forgot" | "reset";
const TITLE: Record<Mode, string> = { login: "Log in", signup: "Create your account", forgot: "Reset your password", reset: "Choose a new password" };
const field = "rounded-full bg-surface px-4 py-3 outline-none focus-visible:ring-2 ring-secondary";

export default function AuthPage({ onAuth }: { onAuth: (u: User) => void }) {
  const token = new URLSearchParams(location.search).get("token");
  const [mode, setMode] = useState<Mode>(token ? "reset" : "login");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [name, setName] = useState("");
  const [msg, setMsg] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const go = (m: Mode) => { setMode(m); setErr(""); setMsg(""); };

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr(""); setMsg("");
    try {
      if (mode === "login") onAuth(await api.login(email, password));
      else if (mode === "signup") onAuth(await api.signup(email, password, name));
      else if (mode === "forgot") { await api.forgot(email); setMsg("If an account exists for that email, a reset link is on its way."); }
      else { await api.reset(token!, password); history.replaceState(null, "", "/"); go("login"); setMsg("Password updated. Log in with your new password."); }
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  const link = (m: Mode, label: string) => <button type="button" className="underline" onClick={() => go(m)}>{label}</button>;

  return (
    <div className="mx-auto flex h-full max-w-sm flex-col items-center justify-center gap-6 px-4">
      <div className="orb orb-idle" style={{ width: "6rem", height: "6rem" }} />
      <h1 className="text-xl font-semibold">{TITLE[mode]}</h1>
      <form onSubmit={submit} className="flex w-full flex-col gap-3">
        {mode === "signup" && <input className={field} placeholder="Your name (optional)" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />}
        {mode !== "reset" && <input className={field} type="email" required placeholder="Email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        {mode !== "forgot" && <input className={field} type="password" required minLength={mode === "login" ? 1 : 8} placeholder={mode === "login" ? "Password" : "Password (8+ characters)"}
          autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} />}
        <p role="status" className="min-h-5 text-sm">{err ? <span className="text-red-400">{err}</span> : <span className="text-muted">{msg}</span>}</p>
        <button disabled={busy} className="rounded-full bg-primary py-3 font-medium text-white disabled:opacity-50">{busy ? "Please wait…" : mode === "forgot" ? "Send reset link" : TITLE[mode]}</button>
      </form>
      <div className="flex gap-4 text-sm text-muted">
        {mode === "login" && <>{link("signup", "Create an account")}{link("forgot", "Forgot password?")}</>}
        {mode === "signup" && link("login", "I already have an account")}
        {(mode === "forgot" || mode === "reset") && link("login", "Back to log in")}
      </div>
    </div>
  );
}
