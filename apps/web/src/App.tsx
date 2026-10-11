import { motion } from "motion/react";
import { DownloadButton, Footer, GithubButton, Nav } from "./Layout";
import { Robot } from "./Robot";
import { Faq } from "./sections/Faq";
import { Features } from "./sections/Features";
import { Hero } from "./sections/Hero";
import { HowItWorks } from "./sections/HowItWorks";
import { Marquee } from "./sections/Marquee";
import { Security } from "./sections/Security";
import { Shapes } from "./sections/Shapes";
import { Sounds } from "./sections/Sounds";
import { Unique } from "./sections/Unique";

export function App() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Marquee />
        <Unique />
        <HowItWorks />
        <Security />
        <Sounds />
        <Features />
        <Shapes />
        <CompareTeaser />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}

function CompareTeaser() {
  return (
    <section className="px-4 py-16 sm:px-6">
      <motion.a
        href="/compare.html"
        whileHover={{ y: -4 }}
        className="glass mx-auto flex max-w-4xl flex-col items-center justify-between gap-4 rounded-3xl px-8 py-8 text-center sm:flex-row sm:text-left"
      >
        <div>
          <p className="text-sm font-semibold text-[var(--accent)]">Sasu vs Siri, ChatGPT, Claude, Raycast, Open Interpreter</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight">See how Sasu compares →</p>
        </div>
        <span className="rounded-full bg-[var(--text)] px-5 py-2.5 text-sm font-medium text-[var(--bg)]">Open comparison</span>
      </motion.a>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="px-4 py-28 text-center sm:px-6">
      <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-80px" }} className="mx-auto flex max-w-2xl flex-col items-center">
        <Robot state="happy" size={120} />
        <h2 className="mt-10 text-4xl font-semibold tracking-tight sm:text-5xl">
          Say <span className="gradient-text">“Hey Sasu”</span>.
        </h2>
        <p className="mt-4 text-lg text-[var(--muted)]">Free and open source. macOS 13+ on Apple Silicon.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <DownloadButton size="lg" />
          <GithubButton label="Star on GitHub" />
        </div>
      </motion.div>
    </section>
  );
}
