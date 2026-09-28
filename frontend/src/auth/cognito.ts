import {
  CognitoUserPool,
  CognitoUserSession,
} from "amazon-cognito-identity-js";

const poolData = {
  UserPoolId:
    (import.meta.env.VITE_COGNITO_USER_POOL_ID as string) || "dummy_pool_id",
  ClientId:
    (import.meta.env.VITE_COGNITO_CLIENT_ID as string) || "dummy_client_id",
};

export const userPool = new CognitoUserPool(poolData);

// ── Local development auth bypass ──────────────────────────────────────────
// Cognito is not connected in local development, so the Vite dev server
// (`npm run dev`) behaves as if a local developer session exists: the
// dashboard treats the visitor as signed in and API calls carry
// DEV_AUTH_TOKEN, which the backend accepts only when it runs with
// DEV_AUTH_BYPASS=1 (backend/src/auth.py).
//
// Production is untouched: `import.meta.env.DEV` is the literal `false` in
// `vite build`, so DEV_AUTH_BYPASS is `false` and every branch guarded by it
// is removed from the bundle. Set VITE_DEV_AUTH_BYPASS=false to exercise the
// real Cognito sign-in flow on the dev server.

/** Marker sent as the bearer token by the dev bypass. Not a credential: it
 *  identifies the request as local development, and a backend without
 *  DEV_AUTH_BYPASS=1 rejects it. */
export const DEV_AUTH_TOKEN = "urbanflow-local-dev";

/** The session the bypass stands in for. Clearly local: no email, no
 *  Cognito identity. */
export const DEV_AUTH_PROFILE = { name: "Local developer", email: "" };

/** Whether the bypass applies under the given Vite environment: only a
 *  development build, and not when explicitly switched off. */
export function devAuthBypassEnabled(env: {
  DEV: boolean;
  VITE_DEV_AUTH_BYPASS?: string;
}): boolean {
  return env.DEV && env.VITE_DEV_AUTH_BYPASS !== "false";
}

export const DEV_AUTH_BYPASS: boolean =
  import.meta.env.DEV &&
  devAuthBypassEnabled({
    DEV: import.meta.env.DEV,
    VITE_DEV_AUTH_BYPASS: import.meta.env.VITE_DEV_AUTH_BYPASS,
  });

export const getCurrentUser = () => {
  return userPool.getCurrentUser();
};

export const getAuthToken = (): Promise<string | null> => {
  if (import.meta.env.DEV && DEV_AUTH_BYPASS) {
    return Promise.resolve(DEV_AUTH_TOKEN);
  }
  return new Promise((resolve, reject) => {
    const user = userPool.getCurrentUser();
    if (!user) {
      resolve(null);
      return;
    }

    user.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err) {
        reject(err);
        return;
      }
      if (session) {
        resolve(session.getIdToken().getJwtToken());
      } else {
        resolve(null);
      }
    });
  });
};
