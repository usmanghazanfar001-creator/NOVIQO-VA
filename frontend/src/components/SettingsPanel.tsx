import { useEffect, useState } from "react";
import * as api from "../services/api";
import type { Reminder, Settings, User } from "../types";

interface P {
  user: User; settings: Settings; onChange(patch: Partial<Settings>): void; onClose(): void;
  onUser(u: User): void; onLoggedOut(): void; onDataDeleted(): void;
}
const box = "flex flex-col gap-2 rounded-2xl bg-bg p-4";
const input = "rounded-full bg-surface px-3 py-2 text-sm outline-none focus-visible:ring-2 ring-secondary";

export default function SettingsPanel({ user, settings, onChange, onClose, onUser, onLoggedOut, onDataDeleted }: P) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [name, setName] = useState(user.name);
  const [note, setNote] = useState("");
  const [cal, setCal] = useState<{ configured: boolean; connected: boolean } | null>(null);
  useEffect(() => { api.calendarStatus().then(setCal).catch(() => {}); }, []);
  const [rems, setRems] = useState<Reminder[]>([]);
  useEffect(() => { api.listReminders().then(setRems).catch(() => {}); }, []);
  useEffect(() => {
    const load = () => setVoices(speechSynthesis.getVoices());
    load(); speechSynthesis.addEventListener("voiceschanged", load);
    return () => speechSynthesis.removeEventListener("voiceschanged", load);
  }, []);
  const run = async (f: () => Promise<unknown>, done: string) => { try { await f(); setNote(done); } catch (e) { setNote((e as Error).message); } };

  return (
    <div className="fixed inset-0 z-30 flex items-end justify-center bg-black/50 sm:items-center" onClick={onClose}>
      <div role="dialog" aria-label="Settings" onClick={(e) => e.stopPropagation()} className="flex max-h-[90%] w-full max-w-lg flex-col gap-3 overflow-y-auto rounded-t-3xl bg-surface p-5 sm:rounded-3xl">
        <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Settings</h2><button className="underline text-sm" onClick={onClose}>Done</button></div>
        <section className={box}><h3 className="font-medium">Voice</h3>
          <label className="flex items-center justify-between gap-3 text-sm">Voice
            <select className={input} value={settings.voice ?? ""} onChange={(e) => onChange({ voice: e.target.value || null })}>
              <option value="">Best available (recommended)</option>{voices.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
            </select></label>
          <label className="flex items-center justify-between gap-3 text-sm">Speaking speed ({settings.speech_rate.toFixed(1)}×)
            <input type="range" min="0.5" max="2" step="0.1" value={settings.speech_rate} onChange={(e) => onChange({ speech_rate: +e.target.value })} /></label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={settings.auto_speak} onChange={(e) => onChange({ auto_speak: e.target.checked })} /> Speak replies to voice questions</label>
        </section>
        <section className={box}><h3 className="font-medium">Appearance</h3>
          <div className="flex gap-2">{(["dark", "light", "system"] as const).map((t) =>
            <button key={t} aria-pressed={settings.theme === t} onClick={() => onChange({ theme: t })}
              className={`flex-1 rounded-full py-1.5 text-sm capitalize ${settings.theme === t ? "bg-primary text-white" : "bg-surface"}`}>{t}</button>)}</div>
        </section>
        <section className={box}><h3 className="font-medium">Privacy</h3>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={settings.memory_enabled} onChange={(e) => onChange({ memory_enabled: e.target.checked })} /> Long-term memory</label>
          <button className="self-start text-sm underline" onClick={() => confirm("Delete all your conversations, notes, memories and settings?") &&
            run(async () => { await api.deleteAllData(); onDataDeleted(); }, "All your data was deleted.")}>Delete all my data</button>
        </section>
        {cal?.configured && <section className={box}><h3 className="font-medium">Calendar</h3>
          {cal.connected ? (<>
            <p className="text-sm text-muted">Google Calendar is connected. Adding an event always asks you first.</p>
            <button className="self-start text-sm underline" onClick={() => run(async () => { await api.disconnectCalendar(); setCal({ ...cal, connected: false }); }, "Calendar disconnected.")}>Disconnect</button>
          </>) : (<>
            <p className="text-sm text-muted">Let NOVIQO read your events and add new ones (you confirm each addition).</p>
            <a className="self-start rounded-full bg-primary px-4 py-1.5 text-sm text-white" href="/api/calendar/connect">Connect Google Calendar</a>
          </>)}
        </section>}
        <section className={box}><h3 className="font-medium">Reminders</h3>
          {rems.length === 0 && <p className="text-sm text-muted">No upcoming reminders. Say “remind me to study at 8 PM”.</p>}
          {rems.map((r) => (
            <div key={r.id} className="flex items-center justify-between gap-2 text-sm">
              <span>{r.text} · {new Date(r.due_at).toLocaleString()}</span>
              <button className="shrink-0 underline" onClick={() => run(async () => { await api.cancelReminder(r.id); setRems((x) => x.filter((y) => y.id !== r.id)); }, "Reminder cancelled.")}>Cancel</button>
            </div>))}
          {"Notification" in window && Notification.permission === "default" &&
            <button className="self-start text-sm underline" onClick={() => Notification.requestPermission().then((p) => setNote(p === "granted" ? "Notifications enabled." : "Notifications stay off."))}>Allow desktop notifications</button>}
        </section>
        <section className={box}><h3 className="font-medium">Account</h3>
          <p className="text-sm text-muted">{user.email}</p>
          <div className="flex gap-2"><input className={`${input} flex-1`} value={name} maxLength={100} aria-label="Your name" onChange={(e) => setName(e.target.value)} />
            <button className="rounded-full bg-surface px-4 text-sm" onClick={() => run(async () => onUser(await api.updateName(name)), "Name saved.")}>Save</button></div>
          <div className="flex gap-4 text-sm">
            <button className="underline" onClick={() => run(async () => { await api.logout(); onLoggedOut(); }, "")}>Log out</button>
            <button className="text-red-400 underline" onClick={() => { const pw = prompt("Enter your password to permanently delete your account"); if (pw) run(async () => { await api.deleteAccount(pw); onLoggedOut(); }, ""); }}>Delete account</button>
          </div>
        </section>
        <p role="status" className="min-h-5 text-sm text-muted">{note}</p>
      </div>
    </div>
  );
}
