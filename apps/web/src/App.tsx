import { themes, type ThemeName } from "@sasu/brand";
import { robotHeadShapes } from "robot-heads";
import { useState } from "react";
import { DownloadButton, Footer, Nav, StarButton } from "./Layout";
import { Robot } from "./Robot";
import { Faq } from "./sections/Faq";
import { Fun } from "./sections/Fun";
import { Guard } from "./sections/Guard";
import { Hero } from "./sections/Hero";
import { SayIt } from "./sections/SayIt";
import { Sounds } from "./sections/Sounds";
import { UndoDemo } from "./sections/UndoDemo";

export function App() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <SayIt />
        <UndoDemo />
        <Guard />
        <Sounds />
        <Fun />
        <Shelf />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}

function Shelf() {
  const [theme, setTheme] = useState<ThemeName>("midnight");
  return (
    <section className="bg-[var(--bg-2)] px-4 py-24 sm:px-6">
      <div className="mx-auto max-w-[1180px]">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h2 className="title text-[clamp(2rem,4vw,3rem)]">Pick a robot.</h2>
            <p className="lede mt-3">Four shapes, four colours. The shape can also show which mode Sasu is in.</p>
          </div>
          <div role="radiogroup" aria-label="Colour" className="flex gap-2.5">
            {(Object.keys(themes) as ThemeName[]).map((t) => (
              <button
                key={t}
                role="radio"
                aria-checked={theme === t}
                aria-label={themes[t].label}
                onClick={() => setTheme(t)}
                className="h-9 w-9 rounded-full transition-transform hover:scale-110"
                style={{ background: themes[t].color, boxShadow: theme === t ? `0 0 0 3px var(--bg-2), 0 0 0 5px ${themes[t].color}` : `inset 0 0 0 3px ${themes[t].trimColor}` }}
              />
            ))}
          </div>
        </div>
        <div className="mt-14 grid grid-cols-2 gap-y-12 border-b-[10px] border-[var(--line-strong)] pb-6 sm:grid-cols-4">
          {robotHeadShapes.map((shape) => (
            <div key={shape} className="flex flex-col items-center gap-4">
              <Robot state="idle" size={120} shape={shape} theme={theme} halo={false} />
              <span className="text-sm font-medium capitalize text-[var(--muted)]">{shape}</span>
            </div>
          ))}
        </div>
        <p className="mt-10 text-[var(--muted)]">
          Wondering how it stacks up against Siri, ChatGPT or Claude?{" "}
          <a href="/compare.html" className="font-semibold text-[var(--accent)] underline-offset-4 hover:underline">
            See the comparison
          </a>
          .
        </p>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="dots px-4 py-32 text-center sm:px-6">
      <div className="mx-auto flex max-w-2xl flex-col items-center">
        <Robot state="happy" size={130} />
        <h2 className="display mt-12 text-[clamp(2.6rem,6vw,4.6rem)]">Say hey to Sasu.</h2>
        <p className="lede mx-auto mt-5">Free, open source, and yours. It takes two minutes to set up.</p>
        <div className="mt-9 flex flex-wrap justify-center gap-3">
          <DownloadButton />
          <StarButton size="lg" />
        </div>
      </div>
    </section>
  );
}
