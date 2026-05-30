"""
QuantumFence - Authentication Routes
Bug fixes:
  - FIX-15: UserOut.from_orm() → UserOut.model_validate() (Pydantic v2)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from database.database import get_db
from database.models import User, UserRole
from config.settings import settings

router = APIRouter()
pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ─── Schemas ─────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.OPERATOR


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserOut


# ─── Helpers ─────────────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    expire    = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire    = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db:    Session = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if not username or payload.get("type") != "access":
            raise exc
    except JWTError:
        raise exc

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise exc
    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ─── Routes ──────────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(400, "Username already registered")
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(400, "Email already registered")

    user = User(
        username        = user_data.username,
        email           = user_data.email,
        hashed_password = hash_password(user_data.password),
        full_name       = user_data.full_name,
        role            = user_data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # FIX-15: Pydantic v2 uses model_validate instead of from_orm
    return UserOut.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(400, "Account is disabled")

    user.last_login = datetime.utcnow()
    db.commit()

    return Token(
        access_token  = create_access_token({"sub": user.username}),
        refresh_token = create_refresh_token({"sub": user.username}),
        token_type    = "bearer",
        user          = UserOut.model_validate(user),  # FIX-15
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.post("/refresh", response_model=Token)
async def refresh_token_endpoint(
    refresh_token: str,
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid refresh token")
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Invalid refresh token")

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(401, "User not found")

    return Token(
        access_token  = create_access_token({"sub": user.username}),
        refresh_token = create_refresh_token({"sub": user.username}),
        token_type    = "bearer",
        user          = UserOut.model_validate(user),  # FIX-15
    )
