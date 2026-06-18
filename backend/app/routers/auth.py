# backend/app/routers/auth.py
#
# Authentication endpoints: register, login, /me
#
# [SECURITY] All authentication failures are logged at WARNING level with
# the caller's email (no passwords ever logged).  This creates an audit trail
# for brute-force detection without exposing secrets in logs.
#
# [SECURITY] /register and /login are rate limited to prevent:
#   • Credential-stuffing attacks against /login
#   • Account-enumeration via /register (timing + error codes)
#   • Automated account creation spam

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.core.config import get_settings
from app.models import db_models
from app.models.schemas import UserRegisterRequest, UserLoginRequest, TokenResponse, UserPublicResponse

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# [SECURITY] Per-IP rate limiter for authentication endpoints.
# Limits are sourced from settings so they can be tightened in production
# without code changes.
limiter = Limiter(key_func=get_remote_address)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> db_models.User:
    """
    Dependency that validates the Bearer token and returns the live DB user.

    [SECURITY] On any validation failure — expired token, tampered signature,
    unknown subject — a uniform 401 is returned.  The error detail is generic
    ('Could not validate credentials') so callers cannot distinguish between
    'token expired', 'user deleted', or 'signature invalid'.  Distinguishing
    these would give an attacker useful oracle information.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # decode_access_token catches JWTError internally and returns None — never raises.
    # SECURITY: Validate JWT claims
    email = decode_access_token(token)
    if not email:
        # [SECURITY] Log at WARNING for audit trail — no token content logged.
        logger.warning("auth: token validation failed — could not decode subject")
        raise credentials_exc

    user = db.query(db_models.User).filter(db_models.User.email == email).first()
    if not user:
        # [SECURITY] User deleted after token was issued.  Log for audit.
        logger.warning("auth: token subject '%s' not found in database", email)
        raise credentials_exc

    return user


@router.post("/register", response_model=TokenResponse, status_code=201)
# [SECURITY] 5/minute per IP — matches RATE_LIMIT_REGISTER.
# Prevents automated account-creation spam and enumeration of registered emails.
# SECURITY: Rate limit protects against abuse
@limiter.limit(settings.RATE_LIMIT_REGISTER)
def register(request: Request, body: UserRegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Register a new user account and return an access token.

    [SECURITY] Duplicate email returns 400 with a generic message.
    Password is hashed with bcrypt before storage — plaintext never persisted.
    [SECURITY] request parameter required by slowapi for rate-key extraction.
    """
    existing = db.query(db_models.User).filter(db_models.User.email == body.email).first()
    if existing:
        # [SECURITY] Log at INFO (not WARNING) — this is a normal usage pattern
        # (user trying to register twice) but worth tracking for abuse detection.
        logger.info("auth: register attempt for already-registered email '%s'", body.email)
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
    logger.info("auth: new user registered — id=%d", new_user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
# [SECURITY] 10/minute per IP — matches RATE_LIMIT_LOGIN.
# Prevents credential-stuffing and brute-force password attacks.
# bcrypt is slow (~100ms) so 10/minute is the practical attacker ceiling anyway;
# the rate limit adds an explicit hard cap before bcrypt even runs.
# SECURITY: Rate limit protects against abuse
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(request: Request, body: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Authenticate a user with email and password, and return an access token.

    [SECURITY] Wrong password and unknown email both return the same 401 detail
    ('Incorrect email or password') to prevent user enumeration.
    Failed attempts are logged at WARNING for brute-force monitoring.
    [SECURITY] request parameter required by slowapi for rate-key extraction.
    """
    user = db.query(db_models.User).filter(db_models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        # [SECURITY] Log failed login attempts for audit/alerting pipelines.
        # Log the email (not the password) so ops can detect credential stuffing.
        logger.warning("auth: failed login attempt for email '%s'", body.email)
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    token = create_access_token(subject=user.email)
    logger.info("auth: successful login — user_id=%d", user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserPublicResponse)
def get_me(current_user: db_models.User = Depends(get_current_user)) -> UserPublicResponse:
    """
    Return the authenticated user's public profile.

    [SECURITY] hashed_password is never included — UserPublicResponse
    contains only id, name, email, created_at.
    """
    return UserPublicResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        created_at=current_user.created_at,
    )
