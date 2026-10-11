import { AppWindow, Calendar, Folder, Globe, Keyboard, Languages, MonitorUp, Music, SlidersHorizontal } from "lucide-react";
import { motion } from "motion/react";

const FEATURES = [
  { Icon: AppWindow, title: "Apps & windows", body: "Open, quit, switch and arrange." },
  { Icon: Folder, title: "Files", body: "Find, move, rename and tidy up." },
  { Icon: SlidersHorizontal, title: "System", body: "Volume, brightness, Wi-Fi, Focus." },
  { Icon: Globe, title: "Web", body: "Search and browse for you." },
  { Icon: MonitorUp, title: "Your screen", body: "Ask about what you're looking at." },
  { Icon: Calendar, title: "Calendar & reminders", body: "Plan your day by voice." },
  { Icon: Music, title: "Music", body: "Spotify and Apple Music control." },
  { Icon: Keyboard, title: "Typing & clicks", body: "Fill forms, press buttons." },
  { Icon: Languages, title: "Tanglish native", body: "Mix English and தமிழ் freely." },
];

export function Features() {
  return (
    <section id="features" className="border-t border-[var(--line)] px-4 py-28 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold text-[var(--accent)]">What it can do</p>
        <h2 className="mt-2 text-4xl font-semibold tracking-tight sm:text-5xl">Your whole Mac, one sentence away.</h2>
        <div className="mt-14 grid grid-cols-1 gap-px overflow-hidden rounded-3xl border border-[var(--line)] bg-[var(--line)] sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ Icon, title, body }, i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.04 }}
              className="group flex items-start gap-4 bg-[var(--bg-2)] p-6 transition-colors hover:bg-[var(--card-solid)]"
            >
              <Icon size={22} className="mt-0.5 shrink-0 text-[var(--accent)] transition-transform group-hover:scale-110" />
              <div>
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-1 text-sm text-[var(--muted)]">{body}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
