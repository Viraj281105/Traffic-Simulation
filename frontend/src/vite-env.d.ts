/// <reference types="vite/client" />

// Vite environment variable type declarations
interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  /** "false" turns off the local development auth bypass on the dev server
   *  (src/auth/cognito.ts). Has no effect on a production build. */
  readonly VITE_DEV_AUTH_BYPASS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
