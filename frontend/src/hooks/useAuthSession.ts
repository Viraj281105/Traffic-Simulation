import { useEffect, useState } from "react";
import type {
  CognitoUserAttribute,
  CognitoUserSession,
} from "amazon-cognito-identity-js";
import {
  DEV_AUTH_BYPASS,
  DEV_AUTH_PROFILE,
  getCurrentUser,
} from "../auth/cognito";

export interface UserProfile {
  name?: string;
  email?: string;
}

/**
 * The signed-in visitor: whether they are signed in, their profile and admin
 * flag, and the sign-in dialog that guards actions needing an account.
 *
 * The local dev server stands in a developer session (auth/cognito.ts); a
 * production build always starts from Cognito.
 */
export function useAuthSession() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    () => DEV_AUTH_BYPASS || !!getCurrentUser(),
  );
  const [showLogin, setShowLogin] = useState<boolean>(false);
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(
    DEV_AUTH_BYPASS ? DEV_AUTH_PROFILE : null,
  );
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    if (DEV_AUTH_BYPASS) return;
    let active = true;
    if (isAuthenticated) {
      const user = getCurrentUser();
      if (user) {
        user.getSession(
          (
            err: Error | null | undefined,
            session: CognitoUserSession | null | undefined,
          ) => {
            if (!err && session) {
              user.getUserAttributes(
                (
                  attrErr: Error | undefined,
                  attributes: CognitoUserAttribute[] | undefined,
                ) => {
                  if (!attrErr && attributes && active) {
                    const profile: Record<string, string> = {};
                    attributes.forEach((attr) => {
                      profile[attr.getName()] = attr.getValue();
                    });
                    const emailStr = profile.email || "";
                    const nameStr =
                      profile.name || (emailStr ? emailStr.split("@")[0] : "");
                    setUserProfile({ name: nameStr, email: emailStr });
                  }
                },
              );
              // Check admin status from backend
              import("../services/api")
                .then(({ get }) => {
                  get<{ isAdmin: boolean }>("/api/me")
                    .then((me) => {
                      if (active) setIsAdmin(me.isAdmin);
                    })
                    .catch(() => {
                      /* non-fatal */
                    });
                })
                .catch(() => {});
            }
          },
        );
      }
    } else {
      // Defer state update to avoid synchronous state update inside effect
      requestAnimationFrame(() => {
        if (active) {
          setUserProfile(null);
          setIsAdmin(false);
        }
      });
    }
    return () => {
      active = false;
    };
  }, [isAuthenticated]);

  /** Runs the action now when signed in; otherwise asks the visitor to sign
   *  in and runs it once they have. */
  const requireAuth = (action: () => void) => {
    if (isAuthenticated) {
      action();
    } else {
      setPendingAction(() => action);
      setShowLogin(true);
    }
  };

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
    setShowLogin(false);
    if (pendingAction) {
      pendingAction();
      setPendingAction(null);
    }
  };

  const signOut = () => {
    const user = getCurrentUser();
    if (user) user.signOut();
    setIsAuthenticated(false);
  };

  return {
    isAuthenticated,
    userProfile,
    isAdmin,
    showLogin,
    openLogin: () => {
      setShowLogin(true);
    },
    closeLogin: () => {
      setShowLogin(false);
    },
    requireAuth,
    handleLoginSuccess,
    signOut,
  };
}
