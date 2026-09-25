import { CognitoUserPool, CognitoUserSession } from 'amazon-cognito-identity-js';

const poolData = {
  UserPoolId: (import.meta.env.VITE_COGNITO_USER_POOL_ID as string) || '',
  ClientId: (import.meta.env.VITE_COGNITO_CLIENT_ID as string) || ''
};

export const userPool = new CognitoUserPool(poolData);

export const getCurrentUser = () => {
  return userPool.getCurrentUser();
};

export const getAuthToken = (): Promise<string | null> => {
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
