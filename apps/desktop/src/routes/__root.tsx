import { createRootRoute, Outlet } from "@tanstack/react-router";
import { MotionConfig } from "motion/react";
import { useThemeVars } from "../robot/useThemeVars";

export const Route = createRootRoute({ component: Root });

function Root() {
  useThemeVars();
  return (
    <MotionConfig reducedMotion="user">
      <Outlet />
    </MotionConfig>
  );
}
