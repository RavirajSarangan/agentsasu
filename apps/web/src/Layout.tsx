import { Download, Moon, Star, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { DOWNLOAD_URL, GITHUB_URL, REPO } from "./config";
import { Github } from "./GithubIcon";
import { Robot } from "./Robot";
import { SoundToggle } from "./sections/SoundToggle";
import { useTheme } from "./theme";

export function DownloadButton({ size = "lg" }: { size?: "sm" | "lg" }) {
  const small = size === "sm" ? "!h-9 !px-4 text-sm" : "";
  if (!DOWNLOAD_URL) {
    return (
      <span className={`btn btn-muted ${small}`} title="The Mac app download is being prepared">
        <Download size={size === "sm" ? 15 : 18} />
        <span className={size === "sm" ? "hidden sm:inline" : ""}>Mac app coming soon</span>
      </span>
    );
  }
  return (
    <a href={DOWNLOAD_URL} className={`btn btn-primary ${small}`}>
      <Download size={size === "sm" ? 15 : 18} />
      <span className={size === "sm" ? "hidden sm:inline" : ""}>Download for Mac</span>
    </a>
  );
}

/** Live star count from GitHub, cached for an hour; falls back to a plain button. */
function useStars(): number | null {
  const [stars, setStars] = useState<number | null>(null);
  useEffect(() => {
    const key = "sasu.stars";
    try {
      const cached = JSON.parse(localStorage.getItem(key) ?? "null") as { n: number; at: number } | null;
      if (cached && Date.now() - cached.at < 3_600_000) {
        setStars(cached.n);
        return;
      }
    } catch {
      /* ignore */
    }
    fetch(`https://api.github.com/repos/${REPO}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { stargazers_count?: number } | null) => {
        if (typeof d?.stargazers_count !== "number") return;
        setStars(d.stargazers_count);
        try {
          localStorage.setItem(key, JSON.stringify({ n: d.stargazers_count, at: Date.now() }));
        } catch {
          /* ignore */
        }
      })
      .catch(() => {});
  }, []);
  return stars;
}

export function StarButton({ size = "sm" }: { size?: "sm" | "lg" }) {
  const stars = useStars();
  if (!GITHUB_URL) return null;
  return (
    <a
      href={GITHUB_URL}
      className={`btn btn-quiet ${size === "sm" ? "!h-9 !px-3.5 text-sm" : ""}`}
      aria-label={`Star Sasu on GitHub${stars !== null ? `, ${stars} stars` : ""}`}
    >
      <Github size={size === "sm" ? 16 : 18} />
      <span className={size === "sm" ? "hidden lg:inline" : ""}>Star on GitHub</span>
      <span className="flex items-center gap-1 rounded-full bg-[var(--bg)] px-2 py-0.5 text-[0.8em] font-semibold tabular-nums">
        <Star size={12} className="text-[var(--amber)]" fill="currentColor" />
        {stars ?? "—"}
      </span>
    </a>
  );
}

export function GithubButton() {
  return <StarButton size="lg" />;
}

function ThemeToggle() {
  const [theme, toggle] = useTheme();
  return (
    <button onClick={toggle} className="flex h-9 w-9 items-center justify-center rounded-full text-[var(--muted)] hover:bg-[var(--panel)] hover:text-[var(--text)]" aria-label={theme === "light" ? "Use dark theme" : "Use light theme"}>
      {theme === "light" ? <Moon size={17} /> : <Sun size={17} />}
    </button>
  );
}

export function Nav({ home = "" }: { home?: string }) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 12);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <header className={`fixed inset-x-0 top-0 z-50 transition-[background,box-shadow] duration-300 ${scrolled ? "bg-[color-mix(in_srgb,var(--bg)_82%,transparent)] shadow-[0_1px_0_var(--line)] backdrop-blur-xl" : ""}`}>
      <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between px-4 sm:px-6">
        <a href={`${home}/#top`} className="flex items-center gap-2.5 text-[1.15rem] font-bold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          <Robot state="idle" size={28} halo={false} interactive={false} />
          Sasu
        </a>
        <nav className="hidden items-center gap-1 text-[0.95rem] text-[var(--muted)] md:flex">
          {[
            ["Say it", `${home}/#say`],
            ["Undo", `${home}/#undo`],
            ["Security", `${home}/#security`],
            ["Fun", `${home}/#fun`],
            ["Compare", "/compare.html"],
          ].map(([label, href]) => (
            <a key={label} href={href} className="rounded-full px-3.5 py-1.5 hover:bg-[var(--panel)] hover:text-[var(--text)]">
              {label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-1.5">
          <SoundToggle />
          <ThemeToggle />
          <StarButton />
        </div>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="dots border-t border-[var(--line)] px-4 py-14 sm:px-6">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-8 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-center gap-3">
          <Robot state="sleeping" size={44} halo={false} interactive={false} />
          <div>
            <p className="font-bold" style={{ fontFamily: "var(--font-display)" }}>
              Sasu
            </p>
            <p className="text-sm text-[var(--muted)]">Free and open source under the MIT license.</p>
          </div>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-[var(--muted)]">
          <a href="/compare.html" className="hover:text-[var(--text)]">
            Compare
          </a>
          {GITHUB_URL && (
            <a href={GITHUB_URL} className="hover:text-[var(--text)]">
              GitHub
            </a>
          )}
          <a href="https://github.com/fayazara/robot-heads" className="hover:text-[var(--text)]">
            Robot by robot-heads
          </a>
        </nav>
      </div>
    </footer>
  );
}
