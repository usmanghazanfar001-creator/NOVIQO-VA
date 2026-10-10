import { useEffect, useRef, useState } from "react";
import AuthPage from "./components/AuthPage";
import Orb from "./components/Orb";
import SettingsPanel from "./components/SettingsPanel";
import Sidebar from "./components/Sidebar";
import * as api from "./services/api";
import { SentenceSpeaker, browserSTT, browserTTS } from "./services/speech";
import { DEFAULT_SETTINGS, type Msg, type Settings, type Status, type User } from "./types";

const HINT: Record<Status, string> = { idle: "How can I help you?", listening: "Listening…", thinking: "Thinking…", speaking: "Speaking…", error: "" };

export default function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined);   // undefined = checking session
  useEffect(() => { api.me().then(setUser).catch(() => setUser(null)); }, []);
  if (user === undefined) return null;
  return user ? <Assistant user={user} setUser={setUser} /> : <AuthPage onAuth={setUser} />;
}

function Assistant({ user, setUser }: { user: User; setUser: (u: User | null) => void }) {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [convId, setConvId] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [sidebar, setSidebar] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [tick, setTick] = useState(0);
  const [pending, setPending] = useState<api.Pending[]>([]);
  const speakerRef = useRef<SentenceSpeaker | null>(null);
  const pendingRef = useRef(pending); pendingRef.current = pending;
  const convIdRef = useRef(convId); convIdRef.current = convId;   // voice callbacks outlive renders
  const [timers, setTimers] = useState<{ id: number; end: number; label: string }[]>([]);
  const [now, setNow] = useState(Date.now());

  const settingsRef = useRef(settings); settingsRef.current = settings;
  useEffect(() => { api.getSettings().then(setSettings).catch(() => {}); }, []);
  useEffect(() => {  // reminders that have come due: show, speak, and notify if the user allowed it
    const check = () => api.dueReminders().then((rs) => rs.forEach((r) => {
      const t = `Reminder: ${r.text}`;
      setMsgs((m) => [...m, { role: "assistant", content: t, via: "voice" }]);
      browserTTS.speak(t, { rate: settingsRef.current.speech_rate, voice: settingsRef.current.voice, onEnd: () => {} });
      if ("Notification" in window && Notification.permission === "granted") new Notification("NOVIQO", { body: r.text });
    })).catch(() => {});
    check(); const i = setInterval(check, 30000); return () => clearInterval(i);
  }, []);
  useEffect(() => {  // landing back from Google's consent screen
    const c = new URLSearchParams(location.search).get("calendar"); if (!c) return;
    history.replaceState(null, "", "/");
    setMsgs([{ role: "assistant", via: "text", content: c === "connected"
      ? "Google Calendar is connected. Try asking what's on your calendar this week." : "I couldn't connect Google Calendar. Please try again from Settings." }]);
  }, []);
  useEffect(() => {  // light / dark / follow the system
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => { document.documentElement.dataset.theme = settings.theme === "system" ? (mq.matches ? "dark" : "light") : settings.theme; };
    apply(); mq.addEventListener("change", apply); return () => mq.removeEventListener("change", apply);
  }, [settings.theme]);
  useEffect(() => { if (!timers.length) return; const i = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(i); }, [timers.length]);
  useEffect(() => { document.getElementById("end")?.scrollIntoView({ behavior: "smooth" }); }, [msgs.length]);

  const fail = (m: string) => { setError(m); setStatus("error"); };
  const handle = (e: unknown) => (e instanceof api.ApiError && e.status === 401 ? setUser(null) : fail((e as Error).message));
  const say = (content: string) => setMsgs((m) => [...m, { role: "assistant", content, via: "text" }]);
  const speak = (t: string, onEnd: () => void) => browserTTS.speak(t, { rate: settings.speech_rate, voice: settings.voice, onEnd });

  function saveSettings(patch: Partial<Settings>) {
    const next = { ...settings, ...patch }; setSettings(next);
    api.putSettings(next).catch((e) => fail((e as Error).message));
  }

  function startTimer(a: api.Action) {
    if (a.type !== "timer") return;
    const id = Date.now() + Math.random();
    setTimers((t) => [...t, { id, end: Date.now() + a.seconds * 1000, label: a.label }]);
    setTimeout(() => {
      const done = `Your ${a.label} timer is done.`;
      setTimers((t) => t.filter((x) => x.id !== id)); say(done); speak(done, () => {});
    }, a.seconds * 1000);
  }

  async function send(content: string, via: Msg["via"]) {
    if (!content.trim()) return;
    const held = pendingRef.current[0];
    if (via === "voice" && held) {   // hands-free answer to a confirmation card
      const w = content.toLowerCase().replace(/[^a-z' ]/g, "").replace(/'/g, "").trim();
      const yes = held.voice_ok && ["yes", "yeah", "yep", "ok", "okay", "confirm", "do it", "go ahead", "yes please"].includes(w);
      const no = ["no", "nope", "cancel", "stop", "dont", "dont do it", "no thanks"].includes(w);
      if (yes || no) { setMsgs((m) => [...m, { role: "user", content, via }]); setStatus("idle"); return decide(held, yes); }
    }
    setMsgs((m) => [...m, { role: "user", content, via }, { role: "assistant", content: "", via }]);
    setError(""); setStatus("thinking");
    const speaker = settings.auto_speak && via === "voice" ? new SentenceSpeaker({ rate: settings.speech_rate, voice: settings.voice }) : null;
    speakerRef.current = speaker;
    const setLast = (f: (t: string) => string) => setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, content: f(x.content) } : x)));
    try {
      const r = await api.chatStream(content, convIdRef.current, via, {
        delta: (t) => { setLast((s) => s + t); if (speaker && !speaker.stopped) { setStatus("speaking"); speaker.push(t); } },
        reset: () => setLast(() => ""),
      });
      setConvId(r.conversation_id); setTick((t) => t + 1);
      r.actions.forEach(startTimer);
      if (r.pending.length) setPending((p) => [...p, ...r.pending]);
      const voiceHold = via === "voice" && r.pending.some((p) => p.voice_ok);
      const hint = " Say yes to confirm, or no to cancel.";
      setLast(() => (voiceHold ? r.reply + hint : r.reply));
      if (speaker) {
        if (voiceHold) speaker.push(hint + " ");
        speaker.finish(() => { setStatus("idle"); if (voiceHold && !speaker.stopped) listen(); });
      } else setStatus("idle");
    } catch (e) {
      speaker?.stop();
      setMsgs((m) => (m.length && m[m.length - 1].role === "assistant" && !m[m.length - 1].content ? m.slice(0, -1) : m));
      handle(e);
    }
  }

  async function decide(p: api.Pending, ok: boolean) {
    setPending((ps) => ps.filter((x) => x.token !== p.token));
    if (!ok) { say("Okay, I won't do that."); if (p.voice_ok) speak("Okay, I won't do that.", () => {}); return; }
    // open the tab inside the click handler so popup blockers allow it, then point it at the URL
    const win = p.tool === "open_url" ? window.open("", "_blank") : null;
    if (win) win.opener = null;
    try {
      const r = await api.confirmAction(p.token);
      r.actions.forEach((a) => {
        if (a.type !== "open_url") return startTimer(a);
        if (win) win.location.href = a.url; else say(`Your browser blocked the new tab. Open it here: ${a.url}`);
      });
      say(r.reply); setTick((t) => t + 1); if (p.voice_ok) speak(r.reply, () => {});
    } catch (e) { win?.close(); say((e as Error).message); }
  }

  function listen() {
    if (!browserSTT.supported) return fail("Voice input isn't supported in this browser. Use Chrome, Edge, or Safari, or type below.");
    setError(""); setStatus("listening");
    let got = false;
    browserSTT.start((t) => { got = true; send(t, "voice"); }, () => { if (!got) setStatus((s) => (s === "listening" ? "idle" : s)); }, fail);
  }

  function orbClick() {
    if (status === "listening") return browserSTT.stop();
    if (status === "speaking") { speakerRef.current?.stop(); browserTTS.cancel(); return setStatus("idle"); }
    if (status === "thinking") return;
    listen();
  }

  const newChat = () => { browserTTS.cancel(); setConvId(null); setMsgs([]); setStatus("idle"); setError(""); setPending([]); };
  async function open(id: string) {
    browserTTS.cancel(); setStatus("idle"); setError(""); setPending([]);
    try { const c = await api.getConv(id); setConvId(id); setMsgs(c.messages); } catch (e) { handle(e); }
  }
  const loggedOut = () => { newChat(); setShowSettings(false); setUser(null); };

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col px-4 pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
      <Sidebar open={sidebar} onClose={() => setSidebar(false)} activeId={convId} tick={tick} onSelect={open} onNew={newChat}
        onDeleted={(id) => id === convId && newChat()} memoryOn={settings.memory_enabled} setMemoryOn={(v) => saveSettings({ memory_enabled: v })} />
      {showSettings && <SettingsPanel user={user} settings={settings} onChange={saveSettings} onClose={() => setShowSettings(false)}
        onUser={setUser} onLoggedOut={loggedOut} onDataDeleted={() => { newChat(); setTick((t) => t + 1); }} />}
      <header className="flex items-center justify-between py-4">
        <div className="flex items-center gap-3">
          <button className="rounded-full bg-surface px-3 py-1 text-sm" onClick={() => setSidebar(true)}>History</button>
          <h1 className="text-xl font-semibold tracking-wide"><span className="text-secondary">N</span>OVIQO</h1>
        </div>
        <div className="flex gap-2 text-sm">
          <button className="rounded-full bg-surface px-3 py-1" onClick={newChat}>New chat</button>
          <button className="rounded-full bg-surface px-3 py-1" onClick={() => setShowSettings(true)}>Settings</button>
        </div>
      </header>

      <main className="flex flex-1 flex-col items-center overflow-hidden">
        <div className="flex flex-col items-center gap-4 py-6">
          <Orb status={status} onClick={orbClick} />
          <p role="status" className="min-h-6 text-muted">{status === "error" ? <span className="text-red-400">{error}</span> : HINT[status]}</p>
          {timers.length > 0 && <div className="flex gap-2 text-sm">{timers.map((t) =>
            <span key={t.id} className="rounded-full bg-surface px-3 py-1 text-secondary">{t.label} · {Math.max(0, Math.ceil((t.end - now) / 1000))}s</span>)}</div>}
        </div>
        <div className="w-full flex-1 space-y-3 overflow-y-auto pb-3">
          {msgs.map((m, i) => (
            <div key={i} className={`max-w-[85%] rounded-2xl px-4 py-2 ${m.role === "user" ? "ml-auto bg-primary text-white" : "bg-surface ring-1 ring-slate-500/20"}`}>{m.content}</div>
          ))}
          <div id="end" />
        </div>
      </main>

      {pending.map((p) => (
        <div key={p.token} role="alertdialog" aria-label="Confirm action" className="mb-2 flex items-center justify-between gap-3 rounded-2xl bg-surface p-3 ring-1 ring-secondary/40">
          <span className="text-sm">{p.summary}</span>
          <span className="flex shrink-0 gap-2 text-sm">
            <button className="rounded-full bg-primary px-4 py-1.5 text-white" onClick={() => decide(p, true)}>Confirm</button>
            <button className="rounded-full bg-bg px-4 py-1.5" onClick={() => decide(p, false)}>Cancel</button>
          </span>
        </div>
      ))}
      <form className="flex gap-2 py-3" onSubmit={(e) => { e.preventDefault(); send(text, "text"); setText(""); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type a message"
          className="flex-1 rounded-full bg-surface px-4 py-3 outline-none ring-1 ring-slate-500/20 focus-visible:ring-2 focus-visible:ring-secondary" />
        <button className="rounded-full bg-primary px-5 font-medium text-white disabled:opacity-40" disabled={status === "thinking" || !text.trim()}>Send</button>
      </form>
    </div>
  );
}
