import { motion } from "motion/react";
import { DownloadButton, StarButton } from "../Layout";
import { Desk } from "./Desk";

export function Hero() {
  return (
    <section id="top" className="relative px-4 pb-24 pt-32 sm:px-6 sm:pt-36">
      <div aria-hidden className="dots pointer-events-none absolute inset-x-0 top-0 h-[560px] [mask-image:linear-gradient(to_bottom,black,transparent)]" />
      <div className="relative mx-auto max-w-[1180px]">
        <div className="grid items-end gap-10 lg:grid-cols-[1.25fr_1fr]">
          <motion.h1
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            className="display text-[clamp(3rem,8.4vw,6.6rem)]"
          >
            Talk to your Mac.
            <span lang="ta" className="mt-4 block text-[0.42em] font-semibold leading-[1.25] tracking-normal text-[var(--muted)]">
              உங்க Mac-கிட்ட பேசுங்க.
            </span>
          </motion.h1>
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.12 }} className="flex flex-col gap-6 pb-2">
            <p className="lede">
              Sasu is a little robot that lives in the corner of your screen. Say “Hey Sasu” in English, Tamil or a mix of both, and it opens apps, sorts files and
              changes settings. It only works for your voice, and anything it does can be undone.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <DownloadButton />
              <StarButton size="lg" />
            </div>
            <p className="text-sm text-[var(--faint)]">Free and open source. Apple Silicon Macs with macOS 13 or later.</p>
          </motion.div>
        </div>
        <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, delay: 0.25, ease: [0.22, 1, 0.36, 1] }} className="mt-16">
          <Desk />
        </motion.div>
      </div>
    </section>
  );
}
