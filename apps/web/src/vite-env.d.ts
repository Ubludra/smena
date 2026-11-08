/// <reference types="vite/client" />
/// <reference types="vitest/config" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_ENABLE_BROWSER_DEMO?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
