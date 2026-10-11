import { FileLock2, FingerprintPattern, HardDrive, Lock, ShieldCheck, UserX } from "lucide-react";
import { motion } from "motion/react";

const ITEMS = [
  { Icon: UserX, title: "Only your voice", body: "Sasu learns your voiceprint on-device and checks every command. Strangers get guest mode — or nothing.", tone: "#ef4444" },
  { Icon: FingerprintPattern, title: "Touch ID for risky actions", body: "Deleting files or changing system settings always needs Touch ID. Voice alone is never enough.", tone: "#a35cf0" },
  { Icon: Lock, title: "Deaf when you're away", body: "The moment your Mac locks, the mic closes and every task is cancelled.", tone: "#f0a020" },
  { Icon: FileLock2, title: "Tamper-evident log", body: "Every action is sealed in a hash-chained log. If anything is edited, Sasu shows it.", tone: "#30c35a" },
  { Icon: HardDrive, title: "Local-first", body: "Wake word, speech and voiceprint stay on your Mac. Run fully offline with a local model.", tone: "#1fb6d8" },
  { Icon: ShieldCheck, title: "Locked down by design", body: "Private 127.0.0.1 channel, a new secret every launch, strict app sandbox rules and no telemetry.", tone: "var(--accent)" },
];

export function Security() {
  return (
    <section id="security" className="relative px-4 py-28 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold text-[var(--accent)]">Security first</p>
        <h2 className="mt-2 max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">Full access to your Mac. Only for you.</h2>
        <p className="mt-4 max-w-xl text-lg text-[var(--muted)]">An agent that can control your computer has to be trustworthy. Sasu is built so nobody else can use it — not people nearby, not websites, not other apps.</p>
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {ITEMS.map(({ Icon, title, body, tone }, i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ delay: (i % 3) * 0.08, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              whileHover={{ y: -4 }}
              className="glass rounded-3xl p-6"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl" style={{ color: tone, background: `color-mix(in srgb, ${tone} 14%, transparent)` }}>
                <Icon size={22} />
              </span>
              <h3 className="mt-5 text-lg font-semibold tracking-tight">{title}</h3>
              <p className="mt-2 leading-relaxed text-[var(--muted)]">{body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
