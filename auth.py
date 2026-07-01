import time
from datetime import datetime, timezone

import requests
from fastapi import Depends, HTTPException, Header
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Signs the OAuth "state" param so we don't need server-side session storage
# for the (short) OAuth handshake. Reuses JWT_SECRET as the signing key.
_state_signer = URLSafeTimedSerializer(settings.JWT_SECRET, salt="oauth-state")


def build_google_auth_url() -> str:
    state = _state_signer.dumps({"t": time.time()})
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


def verify_state(state: str):
    try:
        # state link is only valid for 10 minutes
        _state_signer.loads(state, max_age=600)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")


def exchange_code_for_userinfo(code: str) -> dict:
    token_res = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if not token_res.ok:
        raise HTTPException(status_code=400, detail="Google token exchange failed.")
    access_token = token_res.json().get("access_token")

    userinfo_res = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not userinfo_res.ok:
        raise HTTPException(status_code=400, detail="Failed to fetch Google profile.")
    return userinfo_res.json()


def get_or_create_user(db: Session, userinfo: dict) -> User:
    google_id = userinfo["sub"]
    user = db.query(User).filter(User.google_id == google_id).first()
    if user:
        user.name = userinfo.get("name")
        user.picture = userinfo.get("picture")
        db.commit()
        db.refresh(user)
        return user

    user = User(
        google_id=google_id,
        email=userinfo["email"],
        name=userinfo.get("name"),
        picture=userinfo.get("picture"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_jwt(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "iat": now,
        "exp": now + settings.JWT_EXPIRES,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user
