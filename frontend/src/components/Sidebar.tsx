import { useEffect, useState } from "react";
import * as api from "../services/api";
import type { ConvSummary, Memory } from "../types";

interface P {
  open: boolean; onClose(): void; activeId: string | null; tick: number;
  onSelect(id: string): void; onNew(): void; onDeleted(id: string): void;
  memoryOn: boolean; setMemoryOn(v: boolean): void;
}
const tab = (on: boolean) => `flex-1 rounded-full px-3 py-1.5 text-sm ${on ? "bg-primary text-white" : "bg-bg text-muted"}`;

export default function Sidebar(p: P) {
  const [view, setView] = useState<"chats" | "memory">("chats");
  const [q, setQ] = useState("");
  const [convs, setConvs] = useState<ConvSummary[]>([]);
  const [mems, setMems] = useState<Memory[]>([]);
  const [err, setErr] = useState("");
  const fail = (e: unknown) => setErr((e as Error).message);

  useEffect(() => {  // refresh whenever the drawer opens, the search changes, or a chat completes
    if (!p.open) return;
    const t = setTimeout(() => api.listConvs(q).then(setConvs).catch(fail), q ? 250 : 0);
    return () => clearTimeout(t);
  }, [p.open, q, p.tick]);
  useEffect(() => { if (p.open) api.listMemories().then(setMems).catch(fail); }, [p.open, p.tick]);

  async function rename(c: ConvSummary) {
    const t = prompt("Rename conversation", c.title)?.trim(); if (!t) return;
    try { await api.renameConv(c.id, t.slice(0, 60)); setConvs((cs) => cs.map((x) => (x.id === c.id ? { ...x, title: t.slice(0, 60) } : x))); } catch (e) { fail(e); }
  }
  async function remove(c: ConvSummary) {
    if (!confirm("Delete this conversation?")) return;
    try { await api.deleteConv(c.id); setConvs((cs) => cs.filter((x) => x.id !== c.id)); p.onDeleted(c.id); } catch (e) { fail(e); }
  }
  async function dropMemory(id: number) { try { await api.deleteMemory(id); setMems((m) => m.filter((x) => x.id !== id)); } catch (e) { fail(e); } }
  async function dropAll() { if (confirm("Delete all memories?")) try { await api.clearMemories(); setMems([]); } catch (e) { fail(e); } }

  return (
    <>
      {p.open && <div className="fixed inset-0 z-10 bg-black/50" onClick={p.onClose} />}
      <aside aria-label="History and memory"
        className={`fixed inset-y-0 left-0 z-20 flex w-80 max-w-[85%] flex-col gap-3 bg-surface p-4 shadow-xl transition-transform ${p.open ? "" : "invisible -translate-x-full"}`}>
        <div className="flex gap-2">
          <button className={tab(view === "chats")} aria-pressed={view === "chats"} onClick={() => setView("chats")}>Chats</button>
          <button className={tab(view === "memory")} aria-pressed={view === "memory"} onClick={() => setView("memory")}>Memory</button>
        </div>
        {err && <p className="text-sm text-red-400">{err}</p>}
        {view === "chats" ? (<>
          <button className="rounded-full bg-primary py-2 font-medium text-white" onClick={() => { p.onNew(); p.onClose(); }}>New chat</button>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search conversations" aria-label="Search conversations"
            className="rounded-full bg-bg px-4 py-2 text-sm outline-none focus-visible:ring-2 ring-secondary" />
          <ul className="flex-1 space-y-1 overflow-y-auto">
            {convs.length === 0 && <li className="p-2 text-sm text-muted">{q ? "No conversations match your search." : "No conversations yet. Say something to start one."}</li>}
            {convs.map((c) => (
              <li key={c.id} className={`rounded-xl p-2 ${c.id === p.activeId ? "bg-bg" : ""}`}>
                <button className="block w-full text-left" onClick={() => { p.onSelect(c.id); p.onClose(); }}>
                  <span className="block truncate">{c.title}</span>
                  <span className="text-xs text-muted">{new Date(c.updated_at).toLocaleDateString()} · {c.via}</span>
                </button>
                <div className="mt-1 flex gap-3 text-xs text-muted">
                  <button className="underline" onClick={() => rename(c)}>Rename</button>
                  <button className="underline" onClick={() => remove(c)}>Delete</button>
                </div>
              </li>
            ))}
          </ul>
        </>) : (<>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={p.memoryOn} onChange={(e) => p.setMemoryOn(e.target.checked)} /> Remember things I ask it to</label>
          <ul className="flex-1 space-y-2 overflow-y-auto">
            {mems.length === 0 && <li className="p-2 text-sm text-muted">Nothing saved. Say “remember that I prefer metric units” and it will appear here.</li>}
            {mems.map((m) => (
              <li key={m.id} className="flex items-start justify-between gap-2 rounded-xl bg-bg p-2 text-sm">
                <span>{m.text}</span><button className="shrink-0 underline" onClick={() => dropMemory(m.id)}>Delete</button>
              </li>
            ))}
          </ul>
          {mems.length > 0 && <button className="text-sm underline" onClick={dropAll}>Delete all memories</button>}
        </>)}
        <button className="text-sm text-muted underline" onClick={p.onClose}>Close</button>
      </aside>
    </>
  );
}
