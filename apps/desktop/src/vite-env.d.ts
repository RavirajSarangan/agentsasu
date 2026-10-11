/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Browser-only dev: where `pnpm core:demo` listens. */
  readonly VITE_CORE_URL?: string;
  readonly VITE_CORE_TOKEN?: string;
}
