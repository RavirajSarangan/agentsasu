import { createFileRoute } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { packs } from "@sasu/brand";
import { DanceGlow, FloatingNotes, NowPlaying } from "../robot/DanceFx";
import { ModeChips } from "../robot/ModeChips";
import { startSnapListener } from "../robot/Snap";
import { send } from "../agent/connection";
import { agentStore } from "../agent/store";
import { Bubble } from "../robot/Bubble";
import { Halo } from "../robot/Halo";
import { SasuRobot } from "../robot/SasuRobot";
import { settingsStore } from "../robot/settings";
import { ListeningBars, StateChip } from "../robot/StateChip";
import { authorizeAction, flyHome, flyToApp, haptic, inTauri, onHotkey, showPanel, startDragging } from "../tauri";
import { onAgentEvent } from "../agent/store";

export const Route = createFileRoute("/overlay")({ component: Overlay });

const FESTIVE: Record<string, string> = { pongal: "🌾🍚", deepavali: "🪔✨", puthandu: "🌸", christmas: "🎄", newyear: "🎆" };

function isNight() {
  const h = new Date().getHours();
  return h >= 23 || h < 6;
}

const DRAG_PX = 4;

/**
 * The floating robot. Click = talk, drag = move the window, double-click or
 * right-click = open the panel. Nothing here may clip the robot: its hops and
 * antenna glow draw outside its box.
 */
function Overlay() {
  const down = useRef<{ x: number; y: number } | null>(null);
  const [hover, setHover] = useState(false);
  const state = useSelector(agentStore, (s) => s.view.state);
  const lang = useSelector(agentStore, (s) => s.view.lang);
  const connected = useSelector(agentStore, (s) => s.connection === "open");
  const size = useSelector(settingsStore, (s) => s.size);
  const auth = useSelector(agentStore, (s) => s.view.auth);
  const level = useSelector(agentStore, (s) => s.level);
  const song = useSelector(agentStore, (s) => s.song);
  const focusState = useSelector(agentStore, (s) => s.focus);
  const translating = useSelector(agentStore, (s) => s.translating);
  const festival = useSelector(agentStore, (s) => s.festival);
  useEffect(() => startSnapListener(), []);
  const settings = useSelector(settingsStore);
  const [mood, setMood] = useState<null | "pet" | "dizzy" | "break">(null);
  const [night, setNight] = useState(() => isNight());
  const holdTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const dancing = Boolean(song) && settings.dance && !settings.dnd;
  const asked = useRef<string | null>(null);

  // Dangerous actions: ask Touch ID once per request. The shell sends the verdict to
  // the core itself, so this window never decides anything.
  useEffect(() => {
    if (!auth || asked.current === auth.id) return;
    asked.current = auth.id;
    void authorizeAction(auth.id, auth.reason);
  }, [auth]);

  // First launch: open the setup assistant next to the robot.
  useEffect(() => {
    if (!settingsStore.get().onboarded) showPanel();
  }, []);

  useEffect(() => {
    const offTalk = onHotkey("hotkey-talk", () => send({ type: "ptt_start" }));
    const offStop = onHotkey("hotkey-stop", () => send({ type: "cancel" }));
    const offUndo = onHotkey("hotkey-undo", () => send({ type: "undo" }));
    return () => {
      offTalk();
      offStop();
      offUndo();
    };
  }, []);

  // "Hey Sasu" brings the robot back if it was hidden.
  useEffect(
    () =>
      onAgentEvent((e) => {
        if (e.type !== "wake") return;
        const w = inTauri ? getCurrentWindow() : null;
        void w?.isVisible().then((v) => (v ? undefined : w.show()));
      }),
    [],
  );

  // Shake it (drag fast back and forth) → dizzy. Uses the window's own moves.
  useEffect(() => {
    if (!inTauri) return;
    let last: { x: number; y: number; t: number } | null = null;
    let flips = 0;
    let lastDir = 0;
    let since = 0;
    const off = getCurrentWindow().onMoved(({ payload }) => {
      const now = performance.now();
      if (last) {
        const dx = payload.x - last.x;
        const v = Math.abs(dx) / Math.max(1, now - last.t);
        const dir = Math.sign(dx);
        if (v > 2.5 && dir && dir !== lastDir) {
          if (now - since > 1200) flips = 0;
          flips += 1;
          since = now;
          lastDir = dir;
          if (flips >= 4) {
            flips = 0;
            setMood("dizzy");
            if (settings.sound && !settings.dnd) packs.toon.error();
            setTimeout(() => setMood(null), 2200);
          }
        }
      }
      last = { x: payload.x, y: payload.y, t: now };
    });
    return () => void off.then((u) => u());
  }, [settings.sound, settings.dnd]);

  // Late at night the idle robot gets sleepy.
  useEffect(() => {
    const t = setInterval(() => setNight(isNight()), 60_000);
    return () => clearInterval(t);
  }, []);

  // Break buddy: a gentle stretch / water reminder.
  useEffect(() => {
    if (!settings.breakMinutes) return;
    const t = setInterval(() => {
      setMood("break");
      if (settings.sound && !settings.dnd) packs.kovil.confirm();
      setTimeout(() => setMood(null), 9000);
    }, settings.breakMinutes * 60_000);
    return () => clearInterval(t);
  }, [settings.breakMinutes, settings.sound, settings.dnd]);

  // Feel: fly to the app being worked on, trackpad taps at key moments.
  useEffect(
    () =>
      onAgentEvent((e) => {
        const s = settingsStore.get();
        if (e.type === "focus_app" && s.flyToApps) flyToApp(e.app);
        if (e.type === "turn_done" && s.flyToApps) flyHome();
        if (!s.haptics || s.dnd) return;
        if (e.type === "confirm_request" || e.type === "auth_required") haptic("alignment");
        if (e.type === "turn_done" && e.ok) haptic("level");
      }),
    [],
  );

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    down.current = { x: e.screenX, y: e.screenY };
    // Click and hold = pet
    holdTimer.current = setTimeout(() => {
      down.current = null;
      setMood("pet");
      if (settings.sound && !settings.dnd) packs.soft.success();
      setTimeout(() => setMood(null), 2000);
    }, 600);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = down.current;
    if (d && Math.hypot(e.screenX - d.x, e.screenY - d.y) > DRAG_PX) {
      down.current = null;
      clearTimeout(holdTimer.current);
      startDragging();
    }
  };
  const onPointerUp = () => {
    clearTimeout(holdTimer.current);
    if (down.current) send({ type: "ptt_start" });
    down.current = null;
  };

  const busy = state !== "idle" && state !== "sleeping";
  const shown =
    mood === "pet" ? "happy" : mood === "dizzy" ? "error" : mood === "break" ? "listening" : !busy && dancing ? "happy" : !busy && night ? "sleeping" : state;
  const moodText = mood === "pet" ? "Hehe 💙" : mood === "dizzy" ? "Ayyo! Ellaam suthudhu…" : mood === "break" ? "Break time: konjam thanni kudinga, stretch pannunga 🙆" : null;

  return (
    <main className="flex h-full flex-col items-center justify-end gap-2.5 overflow-visible pb-5" onWheel={(e) => e.preventDefault()}>
      {moodText && !busy ? (
        <motion.p initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="glass max-w-[224px] rounded-[16px] px-3.5 py-2 text-center text-[12.5px]">
          {moodText}
        </motion.p>
      ) : (
        <Bubble />
      )}
      {/* One row of small chips, so they never push the robot out of the window. */}
      <div className="flex max-w-[250px] flex-wrap items-center justify-center gap-1.5 empty:hidden">
        {dancing && !busy && <NowPlaying song={song} />}
        <ModeChips focus={focusState} translating={translating} />
        {festival && !busy && <span className="text-[18px]" aria-label="festival">{FESTIVE[festival] ?? "🎉"}</span>}
      </div>

      <AnimatePresence>
        {(busy || hover || !connected) && (
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 4 }} className="flex items-center gap-2">
            <StateChip state={state} lang={lang} />
            {state === "listening" && <ListeningBars level={level} />}
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        className="relative"
        initial={{ y: -80, opacity: 0, scale: 0.6 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 14, mass: 0.9, delay: 0.15 }}
        onHoverStart={() => setHover(true)}
        onHoverEnd={() => setHover(false)}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onDoubleClick={showPanel}
        onContextMenu={(e) => {
          e.preventDefault();
          showPanel();
        }}
      >
        {dancing && !busy ? <DanceGlow size={size} /> : <Halo state={shown} size={size} />}
        {dancing && !busy && <FloatingNotes size={size} />}
        <motion.div
          animate={
            mood === "dizzy"
              ? { rotate: [0, -14, 12, -10, 8, 0], x: [0, -8, 8, -6, 4, 0] }
              : dancing && !busy
                ? { y: [0, -9, 0], rotate: [0, -5, 5, 0] }
                : { y: 0, rotate: 0, x: 0 }
          }
          transition={mood === "dizzy" ? { duration: 0.8 } : dancing && !busy ? { duration: 0.55, repeat: Infinity } : { duration: 0.3 }}
        >
          <SasuRobot state={shown} speed={dancing && !busy ? 1.5 : undefined} />
        </motion.div>
      </motion.div>

      <AnimatePresence>
        {hover && !busy && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { delay: 0.4 } }}
            exit={{ opacity: 0 }}
            className="glass -mt-1 rounded-full px-2 py-0.5 text-[10.5px] font-medium"
          >
            Say “Hey Sasu”
          </motion.p>
        )}
      </AnimatePresence>
    </main>
  );
}
