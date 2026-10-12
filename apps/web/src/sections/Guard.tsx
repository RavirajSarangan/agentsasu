import { BookLock, Bug, Camera, EyeOff, FileLock2, FingerprintPattern, Ghost, Lock, ShieldCheck, Siren, UserRound, Users, UserX } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { Robot } from "../Robot";
import { cue } from "../sound";

const PROTECTIONS = [
  { Icon: UserRound, title: "Knows your voice", body: "A voiceprint kept encrypted on your Mac. Every command is checked against it." },
  { Icon: FingerprintPattern, title: "Touch ID for risky steps", body: "Deleting, system changes, anything outside your home folder. Voice alone is never enough." },
  { Icon: Bug, title: "Trap files", body: "Sasu plants decoy files. If anything, even a tricked AI, touches them, Sasu locks itself and tells you." },
  { Icon: EyeOff, title: "Leak guard", body: "Text read from files or web pages can't be smuggled out through links or commands." },
  { Icon: Siren, title: "Panic word", body: "Say your secret word and Sasu locks instantly and hides its history until Touch ID." },
  { Icon: Ghost, title: "Intruder log", body: "Anyone who tried while you were away: when, what they said, how close their voice was." },
  { Icon: Lock, title: "Deaf when you're away", body: "Locks with your screen, with fast user switching, and after you've been idle." },
  { Icon: FileLock2, title: "Tamper-evident log", body: "Every action is sealed in a hash chain. If a line is edited, the Security page shows it." },
  { Icon: Users, title: "Family voices", body: "Enrol family and kids. Kids get music, YouTube and jokes; only you can do risky things." },
  { Icon: Camera, title: "Intruder photo", body: "Optional: one camera photo when a stranger tries, or a trap file is touched. Stays on your Mac." },
  { Icon: BookLock, title: "Encrypted memory", body: "“Remember amma's birthday is June 3.” Encrypted, and only your voice can ask for it back." },
];

export function Guard() {
  const [who, setWho] = useState<"owner" | "stranger">("owner");
  const owner = who === "owner";
  return (
    <section id="security" className="cv px-4 py-16 sm:px-6 sm:py-28">
      <div className="mx-auto max-w-[1180px]">
        <div className="grid items-center gap-14 lg:grid-cols-[1fr_1.05fr]">
          <div>
            <h2 className="title text-[clamp(2.2rem,4.6vw,3.6rem)]">It can touch your whole Mac. So it only listens to you.</h2>
            <p className="lede mt-5">An assistant with this much access has to be hard to misuse: by people nearby, by websites, by other apps, and by AI tricks hidden in a file.</p>
          </div>

          <div className="rounded-[28px] bg-[var(--panel)] p-6 shadow-[var(--shadow-lg)] sm:p-8">
            <div role="radiogroup" aria-label="Who is speaking" className="mb-6 inline-flex rounded-full bg-[var(--bg)] p-1">
              {(["owner", "stranger"] as const).map((w) => (
                <button
                  key={w}
                  role="radio"
                  aria-checked={who === w}
                  onClick={() => {
                    setWho(w);
                    cue(w === "owner" ? "confirm" : "error", true);
                  }}
                  className="relative rounded-full px-5 py-2 text-sm font-semibold"
                >
                  {who === w && <motion.span layoutId="who" className="absolute inset-0 rounded-full bg-[var(--panel)] shadow-[var(--shadow-sm)]" />}
                  <span className="relative">{w === "owner" ? "You say it" : "Someone else says it"}</span>
                </button>
              ))}
            </div>
            <p className="text-[1.25rem] font-medium">“Sasu, delete my old screenshots.”</p>
            <div className="mt-6 flex items-start gap-4">
              <Robot state={owner ? "listening" : "error"} size={64} halo={false} interactive={false} />
              <AnimatePresence mode="wait">
                <motion.div key={who} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="min-w-0 flex-1 rounded-2xl bg-[var(--bg)] p-4">
                  {owner ? (
                    <>
                      <p className="flex items-center gap-2 font-semibold">
                        <ShieldCheck size={16} className="text-[var(--signal)]" /> Your voice. Here's the plan:
                      </p>
                      <p className="mt-1.5 text-[var(--muted)]">Throw away 12 screenshots from the Desktop. They go to Sasu's bin, so you can undo it.</p>
                      <p className="mt-3 flex items-center gap-2 text-sm font-semibold text-[var(--accent)]">
                        <FingerprintPattern size={15} /> Confirm with Touch ID
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="flex items-center gap-2 font-semibold">
                        <UserX size={16} className="text-[var(--danger)]" /> Not your voice. Guest mode.
                      </p>
                      <p className="mt-1.5 text-[var(--muted)]">Guests can ask the time or play music. Nothing else runs, and it goes in the intruder log for you.</p>
                    </>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>

        <ul className="mt-20 grid gap-x-10 gap-y-9 sm:grid-cols-2 lg:grid-cols-4">
          {PROTECTIONS.map(({ Icon, title, body }) => (
            <li key={title}>
              <Icon size={22} className="text-[var(--accent)]" />
              <h3 className="mt-3 font-semibold">{title}</h3>
              <p className="mt-1 text-[0.95rem] leading-relaxed text-[var(--muted)]">{body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
