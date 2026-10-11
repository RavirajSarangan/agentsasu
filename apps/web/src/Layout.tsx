import { Download } from "lucide-react";
import { motion, useScroll, useTransform } from "motion/react";
import { DOWNLOAD_URL, GITHUB_URL } from "./config";
import { Github } from "./GithubIcon";
import { Robot } from "./Robot";
import { SoundToggle } from "./sections/SoundToggle";

export function DownloadButton({ size = "sm" }: { size?: "sm" | "lg" }) {
  const cls =
    size === "lg"
      ? "flex h-12 items-center gap-2 rounded-full px-6 font-medium"
      : "flex h-9 items-center gap-1.5 rounded-full px-4 text-sm font-medium";
  if (!DOWNLOAD_URL) {
    return (
      <span className={`${cls} cursor-default bg-[var(--card)] text-[var(--muted)] ring-1 ring-[var(--line)]`} title="The signed Mac app is on its way">
        <Download size={size === "lg" ? 18 : 15} /> <span className={size === "sm" ? "hidden sm:inline" : ""}>Mac app · coming soon</span>
      </span>
    );
  }
  return (
    <a href={DOWNLOAD_URL} className={`${cls} bg-[var(--accent)] text-white shadow-[0_10px_34px_-8px_var(--glow)] transition hover:-translate-y-0.5 hover:brightness-110`}>
      <Download size={size === "lg" ? 18 : 15} /> <span className={size === "sm" ? "hidden sm:inline" : ""}>Download for macOS</span>
    </a>
  );
}

export function GithubButton({ label = "View on GitHub" }: { label?: string }) {
  if (!GITHUB_URL) return null;
  return (
    <a href={GITHUB_URL} className="glass flex h-12 items-center gap-2 rounded-full px-6 font-medium transition hover:-translate-y-0.5">
      <Github size={18} /> {label}
    </a>
  );
}

export function Nav({ home = "" }: { home?: string }) {
  const { scrollY } = useScroll();
  const border = useTransform(scrollY, [0, 40], ["rgba(0,0,0,0)", "var(--line)"]);
  return (
    <motion.header style={{ borderColor: border }} className="fixed inset-x-0 top-0 z-50 border-b backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <a href={`${home}/#top`} className="flex items-center gap-2 font-semibold tracking-tight">
          <Robot state="idle" size={26} halo={false} interactive={false} />
          Sasu
        </a>
        <nav className="hidden items-center gap-7 text-sm text-[var(--muted)] md:flex">
          <a href={`${home}/#unique`} className="hover:text-[var(--text)]">Only on Sasu</a>
          <a href={`${home}/#security`} className="hover:text-[var(--text)]">Security</a>
          <a href={`${home}/#sounds`} className="hover:text-[var(--text)]">Sounds</a>
          <a href="/compare.html" className="hover:text-[var(--text)]">Compare</a>
          <a href={`${home}/#faq`} className="hover:text-[var(--text)]">FAQ</a>
        </nav>
        <div className="flex items-center gap-2">
          <SoundToggle />
          {GITHUB_URL && (
            <a href={GITHUB_URL} aria-label="GitHub" className="hidden h-9 w-9 items-center justify-center rounded-full text-[var(--muted)] hover:text-[var(--text)] sm:flex">
              <Github size={18} />
            </a>
          )}
          <DownloadButton />
        </div>
      </div>
    </motion.header>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-[var(--line)] px-4 py-10 text-sm text-[var(--muted)] sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
        <p>© 2026 Sasu · MIT License · <a href="/compare.html" className="hover:text-[var(--text)]">Compare</a></p>
        <p>
          Robot by{" "}
          <a className="underline-offset-4 hover:underline" href="https://github.com/fayazara/robot-heads">
            robot-heads
          </a>
          . Made with ❤️ for English & தமிழ் speakers.
        </p>
      </div>
    </footer>
  );
}
