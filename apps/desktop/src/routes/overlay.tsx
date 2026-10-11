import { createFileRoute } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { send } from "../agent/connection";
import { agentStore } from "../agent/store";
import { Bubble } from "../robot/Bubble";
import { Halo } from "../robot/Halo";
import { SasuRobot } from "../robot/SasuRobot";
import { settingsStore } from "../robot/settings";
import { ListeningBars, StateChip } from "../robot/StateChip";
import { authorizeAction, flyHome, flyToApp, haptic, onHotkey, showPanel, startDragging } from "../tauri";
import { onAgentEvent } from "../agent/store";

export const Route = createFileRoute("/overlay")({ component: Overlay });

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
    if (e.button === 0) down.current = { x: e.screenX, y: e.screenY };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = down.current;
    if (d && Math.hypot(e.screenX - d.x, e.screenY - d.y) > DRAG_PX) {
      down.current = null;
      startDragging();
    }
  };
  const onPointerUp = () => {
    if (down.current) send({ type: "ptt_start" });
    down.current = null;
  };

  const busy = state !== "idle" && state !== "sleeping";

  return (
    <main className="flex h-full flex-col items-center justify-end gap-2.5 pb-5">
      <Bubble />

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
        <Halo state={state} size={size} />
        <SasuRobot />
      </motion.div>

      <AnimatePresence>
        {hover && !busy && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { delay: 0.4 } }}
            exit={{ opacity: 0 }}
            className="glass -mt-1 rounded-full px-2 py-0.5 text-[10.5px] font-medium"
          >
            Click or ⌥Space to talk
          </motion.p>
        )}
      </AnimatePresence>
    </main>
  );
}
