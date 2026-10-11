import { BellRing, Check, HeartPulse, PhoneCall, Pill, Siren, TriangleAlert, Type } from "lucide-react";
import { Shot } from "./Gallery";

const POINTS = [
  { Icon: Type, title: "Slow Tamil, big text", body: "When an elder speaks, Sasu answers slowly in Tamil, with large captions they can read without glasses." },
  { Icon: Pill, title: "Medicine reminders", body: "“Amma-ku 8 mani BP maathirai reminder vai.” At 8 Sasu asks, listens for “ஆமா”, and asks again after 15 minutes." },
  { Icon: BellRing, title: "Missed-dose alert", body: "Still no answer? You get a text, so you can call and check in. The schedule is encrypted on the Mac." },
  { Icon: PhoneCall, title: "Call family by voice", body: "“மகனுக்கு போன் பண்ணு” finds the son in Contacts and starts a FaceTime audio call, after a spoken yes." },
  { Icon: Siren, title: "Say “udhavi” for help", body: "“Help / உதவி” starts a 10-second spoken countdown they can cancel, then texts the emergency contact." },
];

const DOSES = [
  { time: "8:00 AM", who: "Amma", what: "BP மாத்திரை", status: "taken" },
  { time: "1:30 PM", who: "Appa", what: "sugar tablet", status: "missed" },
  { time: "9:00 PM", who: "Amma", what: "vitamin D", status: "later" },
] as const;

export function Amma() {
  return (
    <section id="amma" className="px-4 py-28 sm:px-6">
      <div className="mx-auto grid max-w-[1180px] items-center gap-14 lg:grid-cols-[1.05fr_1fr]">
        <div>
          <p className="flex items-center gap-2 text-sm font-semibold text-[var(--accent)]">
            <HeartPulse size={16} /> Amma mode
          </p>
          <h2 className="title mt-3 text-[clamp(2.2rem,4.6vw,3.6rem)]">Looks after the people who looked after you.</h2>
          <p className="lede mt-5">Enrol your parents' voices as Elder. Sasu speaks to them the way they speak, and tells you when something needs you.</p>
          <ul className="mt-10 grid gap-x-8 gap-y-7 sm:grid-cols-2">
            {POINTS.map(({ Icon, title, body }) => (
              <li key={title}>
                <p className="flex items-center gap-2 font-semibold">
                  <Icon size={17} className="text-[var(--accent)]" /> {title}
                </p>
                <p className="mt-1.5 text-[0.95rem] text-[var(--muted)]">{body}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative flex flex-col items-center gap-6">
          <Shot
            name="robot-amma"
            alt="The Sasu robot asking in large Tamil text: “அம்மா, BP மாத்திரை நேரம். சாப்பிட்டீங்களா?” (Amma, it's time for your BP tablet. Have you taken it?)"
            width={270}
            height={285}
            className="h-auto w-full max-w-[300px]"
          />
          <div className="w-full max-w-[420px] rounded-[22px] bg-[var(--panel)] p-5 shadow-[var(--shadow-lg)]">
            <p className="flex items-center gap-2 text-sm font-semibold">
              <HeartPulse size={15} className="text-[var(--accent)]" /> Care today
            </p>
            <ul className="mt-3 flex flex-col gap-1.5">
              {DOSES.map((d) => (
                <li key={d.time} className="flex items-center gap-3 rounded-xl bg-[var(--bg)] px-3 py-2 text-sm">
                  <span className="w-[62px] tabular-nums text-[var(--muted)]">{d.time}</span>
                  <span className="min-w-0 flex-1 truncate">
                    <b className="font-semibold">{d.who}</b> · {d.what}
                  </span>
                  {d.status === "taken" ? (
                    <span className="flex items-center gap-1 text-xs font-semibold text-[var(--signal)]">
                      <Check size={12} strokeWidth={3} /> Taken
                    </span>
                  ) : d.status === "missed" ? (
                    <span className="flex items-center gap-1 text-xs font-semibold text-[var(--danger)]">
                      <TriangleAlert size={12} /> Texted you
                    </span>
                  ) : (
                    <span className="text-xs font-semibold text-[var(--muted)]">Later</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
