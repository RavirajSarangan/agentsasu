const COMMANDS = [
  ["Open Safari and search flights to Chennai", "en"],
  ["Downloads la irukura PDF ellam list pannu", "en"],
  ["நாளைக்கு 9 மணிக்கு reminder வை", "ta"],
  ["Turn on Do Not Disturb for an hour", "en"],
  ["Spotify-ல Ilaiyaraaja songs போடு", "ta"],
  ["What's using all my battery?", "en"],
  ["Screenshot-ஐ Desktop-ல save பண்ணு", "ta"],
  ["Move this week's invoices to a folder", "en"],
] as const;

export function Marquee() {
  const row = [...COMMANDS, ...COMMANDS];
  return (
    <section aria-label="Things you can say" className="relative overflow-hidden border-y border-[var(--line)] py-5 [mask-image:linear-gradient(90deg,transparent,black_10%,black_90%,transparent)]">
      <div className="marquee flex w-max gap-3">
        {row.map(([text, lang], i) => (
          <span key={i} lang={lang} className="glass whitespace-nowrap rounded-full px-4 py-2 text-sm text-[var(--muted)]">
            “{text}”
          </span>
        ))}
      </div>
    </section>
  );
}
