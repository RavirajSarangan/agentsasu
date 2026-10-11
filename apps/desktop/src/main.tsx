import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createHashHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { startAgent } from "./agent/connection";
import { startSoundPlayer } from "./sound/player";
import { inTauri, windowLabel } from "./tauri";
import { routeTree } from "./routeTree.gen";
import "./styles/index.css";

// Hash history: Tauri serves index.html for each window, the hash picks the route.
const router = createRouter({ routeTree, history: createHashHistory() });
const queryClient = new QueryClient();

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

// Each Tauri window loads index.html; its label ("overlay" | "panel") picks the route.
if (!location.hash && windowLabel) location.hash = `#/${windowLabel}`;
const root = document.documentElement.classList;
if (inTauri) root.add("native");
root.add(location.hash.startsWith("#/overlay") ? "overlay" : "panel");

startAgent();
startSoundPlayer();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
