/// <reference types="vite/client" />

// Vite environment variable type declarations
interface ImportMetaEnv {
  readonly VITE_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
