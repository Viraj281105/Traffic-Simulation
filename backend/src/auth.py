import os
import json
import urllib.request
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwk, jwt
from jose.utils import base64url_decode
import time

security = HTTPBearer()

REGION = os.getenv("AWS_REGION", "us-east-1")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")

# Cache the keys so we don't fetch them on every request
_JWKS_CACHE = None

def get_jwks():
    global _JWKS_CACHE
    if _JWKS_CACHE is None:
        if not USER_POOL_ID or not REGION:
            raise ValueError("COGNITO_USER_POOL_ID or AWS_REGION is not set")
        
        keys_url = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
        with urllib.request.urlopen(keys_url) as response:
            _JWKS_CACHE = json.loads(response.read().decode("utf-8"))['keys']
    return _JWKS_CACHE

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing"
        )
        
    if not USER_POOL_ID:
        # For local dev without Cognito, you can bypass by returning a dummy user if preferred,
        # but here we require it.
        raise HTTPException(status_code=500, detail="Cognito User Pool ID not configured on server")

    try:
        # Get the key ID from the header
        headers = jwt.get_unverified_headers(token)
        kid = headers.get('kid')
        
        # Find the public key matching the kid
        keys = get_jwks()
        key_index = -1
        for i in range(len(keys)):
            if kid == keys[i]['kid']:
                key_index = i
                break
                
        if key_index == -1:
            raise HTTPException(status_code=401, detail="Public key not found in jwks.json")
            
        public_key = jwk.construct(keys[key_index])
        
        # Get the payload
        message, encoded_signature = str(token).rsplit('.', 1)
        decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
        
        # Verify signature
        if not public_key.verify(message.encode("utf8"), decoded_signature):
            raise HTTPException(status_code=401, detail="Signature verification failed")
            
        # Verify claims
        claims = jwt.get_unverified_claims(token)
        if time.time() > claims['exp']:
            raise HTTPException(status_code=401, detail="Token is expired")
            
        # Optional: verify audience (client ID)
        if claims.get('aud') != CLIENT_ID and claims.get('client_id') != CLIENT_ID:
            raise HTTPException(status_code=401, detail="Token was not issued for this audience")
            
        return claims
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")

def get_current_user_id(claims: dict = Security(verify_token)) -> str:
    """Returns the Cognito username (sub) from the token."""
    return claims.get("sub")
