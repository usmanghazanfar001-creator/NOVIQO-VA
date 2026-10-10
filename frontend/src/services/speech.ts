export interface SpeechProvider {
  supported: boolean;
  start(onResult: (text: string) => void, onEnd: () => void, onError: (msg: string) => void): void;
  stop(): void;
}
export interface TTSProvider {
  speak(text: string, o: { rate: number; voice?: string | null; onEnd: () => void }): void;
  cancel(): void;
}

const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

export const browserSTT: SpeechProvider = (() => {
  let rec: any;
  return {
    supported: !!SR,
    start(onResult, onEnd, onError) {
      rec = new SR(); rec.lang = navigator.language || "en-US"; rec.interimResults = false;
      rec.onresult = (e: any) => onResult(e.results[0][0].transcript);
      rec.onerror = (e: any) => onError(
        e.error === "not-allowed" ? "Microphone access was denied. Allow it in your browser settings."
        : e.error === "no-speech" ? "I didn't hear anything. Try again." : "Speech recognition failed. Try again or type instead.");
      rec.onend = onEnd; rec.start();
    },
    stop() { rec?.stop(); },
  };
})();

export const browserTTS: TTSProvider = {
  speak(text, { rate, voice, onEnd }) {
    const u = new SpeechSynthesisUtterance(text); u.rate = rate; u.onend = onEnd; u.onerror = onEnd;
    const v = pickVoice(voice); if (v) u.voice = v;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
  },
  cancel() { speechSynthesis.cancel(); },
};

/** A chosen voice by name, or (no name) the most natural one for the browser's language: Edge's "Natural"/"Online"
 *  neural voices and Chrome's Google voices sound far better than the default system voice. */
export function pickVoice(name?: string | null): SpeechSynthesisVoice | undefined {
  const vs = speechSynthesis.getVoices();
  if (name) return vs.find((v) => v.name === name);
  const lang = (navigator.language || "en-US").toLowerCase().split("-")[0];
  const score = (v: SpeechSynthesisVoice) => (v.lang.toLowerCase().startsWith(lang) ? 100 : 0)
    + (/natural|neural|online/i.test(v.name) ? 50 : /google/i.test(v.name) ? 20 : 0) + (v.default ? 1 : 0);
  return [...vs].sort((a, b) => score(b) - score(a))[0];
}

/** Text for the speech engine: no markdown symbols, and links are not read out character by character. */
export const speakable = (t: string) => t.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/https?:\/\/\S+/g, "a link")
  .replace(/[*_`#>~|]/g, "").replace(/\s+/g, " ").trim();

/** Speaks a streaming reply sentence by sentence, so speech starts before the model has finished writing. */
export class SentenceSpeaker {
  stopped = false;
  private buf = ""; private open = 0; private finished = false; private done: () => void = () => {};
  constructor(private o: { rate: number; voice?: string | null }) {}

  push(delta: string) {
    if (this.stopped) return;
    this.buf += delta;
    const re = /[.!?]["')\]]*\s+|\n+/g; let last = 0, m: RegExpExecArray | null;
    while ((m = re.exec(this.buf))) {            // a sentence ends at . ! ? followed by space; "3.14" and "Dr." stay together
      const end = m.index + m[0].length;
      const chunk = this.buf.slice(last, end);
      if (end - last >= 25 && !/\b(Dr|Mr|Mrs|Ms|Prof|St|vs|e\.g|i\.e|etc)\.\s+$/i.test(chunk)) { this.say(chunk); last = end; }
    }
    this.buf = this.buf.slice(last);
  }
  finish(done: () => void) { this.done = done; this.finished = true; if (this.buf.trim()) this.say(this.buf); this.buf = ""; this.check(); }
  stop() { this.stopped = true; speechSynthesis.cancel(); }

  private say(t: string) {
    const s = speakable(t); if (!s || this.stopped) return;
    const u = new SpeechSynthesisUtterance(s); u.rate = this.o.rate;
    const v = pickVoice(this.o.voice); if (v) u.voice = v;
    this.open++; u.onend = u.onerror = () => { this.open--; this.check(); };
    speechSynthesis.speak(u);                    // utterances queue up and play in order
  }
  private check() { if (this.finished && this.open <= 0) { this.finished = false; this.done(); } }
}
