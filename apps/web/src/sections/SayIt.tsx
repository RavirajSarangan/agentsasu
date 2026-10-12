import { Volume2 } from "lucide-react";
import { useState } from "react";

const LINES: { text: string; lang: "en" | "ta" | "mix"; does: string }[] = [
  { text: "Hey Sasu, open Safari and look up flights to Chennai", lang: "en", does: "Opens Safari and searches" },
  { text: "Downloads la irukura PDF ellam oru folder-la podu", lang: "mix", does: "Finds the PDFs, shows the plan, moves them" },
  { text: "நாளைக்கு காலையில அம்மாவுக்கு போன் பண்ண நினைவூட்டு", lang: "ta", does: "Adds a reminder for tomorrow morning" },
  { text: "Spotify-la next song podu, volume konjam kammi pannu", lang: "mix", does: "Skips the song, turns the volume down" },
  { text: "Good morning", lang: "en", does: "Weather, today's meetings and reminders, in one breath" },
  { text: "Focus 25 minutes", lang: "en", does: "Closes distractions, then puts everything back when time's up" },
  { text: "இது என்ன?", lang: "ta", does: "Looks at your screen and explains it in Tamil" },
  { text: "Translate mode", lang: "en", does: "You speak Tamil, Sasu says it in English, and back" },
  { text: "Inniku Rahu kaalam eppo?", lang: "mix", does: "Rahu kaalam, thithi and the Tamil date for your city" },
  { text: "Sasu, undo", lang: "en", does: "Puts back whatever it just changed" },
];

const LANG_LABEL = { en: "English", ta: "தமிழ்", mix: "Tanglish" };

function speak(text: string, lang: "en" | "ta" | "mix", onEnd: () => void) {
  const synth = window.speechSynthesis;
  if (!synth) return onEnd();
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const want = lang === "ta" ? "ta" : "en-IN";
  const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(want.toLowerCase())) ?? synth.getVoices().find((v) => v.lang.startsWith("en"));
  if (voice) u.voice = voice;
  u.lang = lang === "ta" ? "ta-IN" : "en-IN";
  u.rate = 0.98;
  u.onend = onEnd;
  u.onerror = onEnd;
  synth.speak(u);
}

export function SayIt() {
  const [playing, setPlaying] = useState<number | null>(null);
  return (
    <section id="say" className="cv px-4 py-16 sm:px-6 sm:py-28">
      <div className="mx-auto grid max-w-[1180px] grid-cols-[minmax(0,1fr)] gap-14 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <h2 className="title text-[clamp(2.2rem,4.6vw,3.6rem)]">Say it the way you'd say it to a friend.</h2>
          <p className="lede mt-5">
            No commands to learn. English, Tamil, or the mix most of us actually speak. Sasu answers in the same language you used, with the Mac's own Tamil and English voices.
          </p>
        </div>
        <ul className="divide-y divide-[var(--line)] border-y border-[var(--line)]">
          {LINES.map((l, i) => (
            <li key={l.text} className="flex items-center gap-5 py-5">
              <button
                onClick={() => {
                  setPlaying(i);
                  speak(l.text, l.lang, () => setPlaying((p) => (p === i ? null : p)));
                }}
                className="key flex h-12 w-12 shrink-0 items-center justify-center text-[var(--accent)]"
                data-pressed={playing === i}
                aria-label={`Hear “${l.text}”`}
              >
                <Volume2 size={18} className={playing === i ? "blink" : ""} />
              </button>
              <div className="min-w-0">
                <p lang={l.lang === "ta" ? "ta" : "en"} className="text-[1.15rem] font-medium leading-snug sm:text-[1.3rem]">
                  “{l.text}”
                </p>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  <span className="font-semibold text-[var(--text)]">{LANG_LABEL[l.lang]}.</span> {l.does}.
                </p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
