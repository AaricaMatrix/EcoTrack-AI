# backend/app/routers/auth.py — hardened against replay attacks
# Added: logout endpoint that blacklists JWT, brute force protection

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password,
    create_access_token, decode_access_token, blacklist_token
)
from app.core.config import get_settings
from app.models import db_models
from app.models.schemas import (
    UserRegisterRequest, UserLoginRequest,
    TokenResponse, UserPublicResponse
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Failed login tracker — prevents brute force (LPDoS + credential stuffing)
# Key: email, Value: (attempt_count, first_attempt_timestamp)
_failed_attempts: dict = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300   # 5 minutes lockout


def _check_brute_force(email: str) -> None:
    """
    Block repeated failed login attempts — prevents:
    - Brute force attacks
    - Credential stuffing
    - LPDoS via login endpoint flooding (complements rate limiter)
    """
    import time
    now = time.time()
    if email in _failed_attempts:
        count, first_time = _failed_attempts[email]
        # Reset counter after lockout period
        if now - first_time > LOCKOUT_SECONDS:
            del _failed_attempts[email]
            return
        # Block if too many attempts
        if count >= MAX_FAILED_ATTEMPTS:
            remaining = int(LOCKOUT_SECONDS - (now - first_time))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Try again in {remaining} seconds.",
            )


def _record_failed_attempt(email: str) -> None:
    import time
    now = time.time()
    if email in _failed_attempts:
        count, first = _failed_attempts[email]
        _failed_attempts[email] = (count + 1, first)
    else:
        _failed_attempts[email] = (1, now)


def _clear_failed_attempts(email: str) -> None:
    _failed_attempts.pop(email, None)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> db_models.User:
    """
    Validate JWT and return User.
    Checks: signature, expiry, blacklist (logout replay prevention).
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    email = decode_access_token(token)  # Returns None if expired or blacklisted
    if not email:
        raise credentials_exc
    user = db.query(db_models.User).filter(db_models.User.email == email).first()
    if not user:
        raise credentials_exc
    return user


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: UserRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(db_models.User).filter(db_models.User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = db_models.User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    settings = get_settings()
    token = create_access_token(subject=new_user.email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: UserLoginRequest, db: Session = Depends(get_db)):
    # Check brute force lockout before hitting DB
    _check_brute_force(body.email)

    user = db.query(db_models.User).filter(db_models.User.email == body.email).first()

    # Same error for wrong email AND wrong password — prevents user enumeration
    if not user or not verify_password(body.password, user.hashed_password):
        _record_failed_attempt(body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login — clear failed attempt counter
    _clear_failed_attempts(body.email)
    settings = get_settings()
    token = create_access_token(subject=user.email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=200)
def logout(
    token: str = Depends(oauth2_scheme),
    current_user: db_models.User = Depends(get_current_user),
):
    """
    Logout endpoint — blacklists the JWT token.
    Prevents replay attacks where attacker captures and reuses a valid token.
    After logout, the token is invalid even before expiry.
    """
    blacklist_token(token)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserPublicResponse)
def get_me(current_user: db_models.User = Depends(get_current_user)):
    return UserPublicResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        created_at=current_user.created_at,
    )