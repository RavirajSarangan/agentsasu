import {
  Brain,
  CircleCheck,
  Ear,
  type LucideIcon,
  MessageCircle,
  Moon,
  Search,
  Sparkles,
  TriangleAlert,
  Wrench,
} from "lucide-react";
import type { RobotHeadState } from "robot-heads";

export type StateStyle = { label: string; ta: string; color: string; Icon: LucideIcon };

/** One colour + icon per robot state, used by the chip, halo and timeline. */
export const STATE_STYLE: Record<RobotHeadState, StateStyle> = {
  idle: { label: "Ready", ta: "தயார்", color: "var(--accent)", Icon: Sparkles },
  listening: { label: "Listening", ta: "கேட்கிறேன்", color: "#30c35a", Icon: Ear },
  thinking: { label: "Thinking", ta: "யோசிக்கிறேன்", color: "#f0a020", Icon: Brain },
  searching: { label: "Searching", ta: "தேடுகிறேன்", color: "#1fb6d8", Icon: Search },
  working: { label: "Working", ta: "செய்கிறேன்", color: "var(--accent)", Icon: Wrench },
  speaking: { label: "Speaking", ta: "பேசுகிறேன்", color: "#a35cf0", Icon: MessageCircle },
  happy: { label: "Done", ta: "முடிந்தது", color: "#30c35a", Icon: CircleCheck },
  error: { label: "Problem", ta: "பிரச்சனை", color: "#ef4444", Icon: TriangleAlert },
  sleeping: { label: "Sleeping", ta: "தூங்குகிறேன்", color: "#8e8e93", Icon: Moon },
};
