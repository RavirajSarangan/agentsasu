import { useQuery } from "@tanstack/react-query";
import { useSelector } from "@tanstack/react-store";
import { CalendarDays, Moon, Sparkles, Sunrise, Sunset } from "lucide-react";
import { apiGet } from "../agent/connection";
import { agentStore } from "../agent/store";
import { settingsStore } from "../robot/settings";
import { Card } from "../ui/Card";

type Panchangam = {
  date: string;
  city: string;
  approximate: boolean;
  sunrise: string;
  sunset: string;
  rahu: [string, string];
  yama: [string, string];
  kuligai: [string, string];
  abhijit: [string, string];
  tamil: { en: string; ta: string };
  thithi: { en: string; ta: string; n: number };
};

/** Times as the place shows them ("7:27"), not converted to this Mac's zone. */
const hm = (iso: string) => {
  const [h, m] = iso.slice(11, 16).split(":").map(Number);
  return `${h! % 12 || 12}:${String(m).padStart(2, "0")}`;
};
const span = (s: [string, string]) => `${hm(s[0])}–${hm(s[1])}`;

/** Home: today's Tamil date, thithi, Rahu kaalam and friends (Settings → Personal). */
export function TodayCard() {
  const on = useSelector(settingsStore, (s) => s.panchangam);
  const city = useSelector(settingsStore, (s) => s.city);
  const connected = useSelector(agentStore, (s) => s.connection === "open");
  const today = useQuery({
    queryKey: ["panchangam", city],
    queryFn: () => apiGet<Panchangam>("/api/panchangam"),
    enabled: connected && on,
    refetchInterval: 30 * 60_000,
  });
  const p = today.data;
  if (!on || !p) return null;
  // the ISO times carry the place's offset, so this compares real moments
  const now = Date.now();
  const inRahu = !p.approximate && Date.parse(p.rahu[0]) <= now && now < Date.parse(p.rahu[1]);
  const rows = [
    { label: "Rahu kaalam", ta: "ராகு காலம்", value: span(p.rahu), warn: true },
    { label: "Yamagandam", ta: "எமகண்டம்", value: span(p.yama), warn: true },
    { label: "Kuligai", ta: "குளிகை", value: span(p.kuligai), warn: false },
    { label: "Abhijit", ta: "அபிஜித்", value: span(p.abhijit), warn: false },
  ];
  return (
    <Card className="flex flex-col gap-3 px-5 py-4">
      <div className="flex items-center gap-2">
        <CalendarDays size={15} className="text-[var(--accent)]" />
        <p className="text-[13px] font-semibold">
          <span lang="ta">{p.tamil.ta}</span> · <span lang="ta">{p.thithi.ta}</span>
        </p>
        {(p.thithi.n === 15 || p.thithi.n === 30) && <Moon size={13} className="text-[var(--warn)]" aria-label={p.thithi.en} />}
        <span className="ml-auto flex items-center gap-2.5 text-[11.5px] tabular-nums text-[var(--muted)]">
          <span className="flex items-center gap-1">
            <Sunrise size={12} /> {hm(p.sunrise)}
          </span>
          <span className="flex items-center gap-1">
            <Sunset size={12} /> {hm(p.sunset)}
          </span>
        </span>
      </div>
      <ul className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        {rows.map((r) => (
          <li
            key={r.label}
            className="rounded-[8px] bg-[var(--sunken)] px-3 py-2"
            style={r.label === "Rahu kaalam" && inRahu ? { boxShadow: "inset 0 0 0 1.5px var(--warn)" } : undefined}
          >
            <p className="text-[11px] text-[var(--muted)]">
              <span lang="ta">{r.ta}</span>
            </p>
            <p className="text-[13px] font-semibold tabular-nums" style={{ color: r.warn ? "var(--text)" : "var(--ok)" }}>
              {r.value}
            </p>
          </li>
        ))}
      </ul>
      <p className="flex items-center gap-1 text-[11px] text-[var(--faint)]">
        <Sparkles size={11} />
        {p.approximate ? "Approximate (6 AM–6 PM). Set your home city in Settings → Personal for exact times." : `For ${p.city}, worked out on this Mac.`}
        {inRahu && <span className="ml-1 font-semibold text-[var(--warn)]">Rahu kaalam now</span>}
      </p>
    </Card>
  );
}
