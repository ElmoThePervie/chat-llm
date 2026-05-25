import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User
from app.redis_client import redis_client
from app.schemas.auth import TokenPair, UserCreate, UserLogin

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()

REFRESH_KEY_PREFIX = "refresh:"


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: UserCreate) -> User:
        existing = await self.db.scalar(select(User).where(User.login == data.login))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already taken")
        if data.email:
            email_taken = await self.db.scalar(select(User).where(User.email == data.email))
            if email_taken:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already taken")

        user = User(
            login=data.login,
            email=data.email,
            password_hash=pwd_context.hash(data.password),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(self, data: UserLogin) -> User:
        user = await self.db.scalar(select(User).where(User.login == data.login))
        if not user or not user.password_hash:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not pwd_context.verify(data.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return user

    def create_tokens(self, user: User) -> TokenPair:
        access = self._create_access_token(user.id)
        refresh = self._create_refresh_token(user.id)
        return TokenPair(access_token=access, refresh_token=refresh)

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        key = f"{REFRESH_KEY_PREFIX}{refresh_token}"
        user_id = redis_client.get(key)
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user = await self.db.get(User, int(user_id))
        if not user:
            redis_client.delete(key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        redis_client.delete(key)
        return self.create_tokens(user)

    def logout(self, refresh_token: str) -> None:
        redis_client.delete(f"{REFRESH_KEY_PREFIX}{refresh_token}")

    async def github_callback(self, code: str) -> User:
        if not settings.github_client_id or not settings.github_client_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub OAuth not configured",
            )

        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_redirect_uri,
                },
            )
            token_resp.raise_for_status()
            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub auth failed")

            user_resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            user_resp.raise_for_status()
            gh_user = user_resp.json()

        github_id = str(gh_user["id"])
        login = gh_user.get("login") or f"github_{github_id}"
        email = gh_user.get("email")

        user = await self.db.scalar(select(User).where(User.github_id == github_id))
        if user:
            return user

        if email:
            user = await self.db.scalar(select(User).where(User.email == email))
            if user:
                user.github_id = github_id
                await self.db.commit()
                await self.db.refresh(user)
                return user

        base_login = login[:50]
        candidate = base_login
        n = 1
        while await self.db.scalar(select(User).where(User.login == candidate)):
            candidate = f"{base_login}_{n}"[:64]
            n += 1

        user = User(login=candidate, email=email, github_id=github_id, password_hash=None)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    def _create_access_token(self, user_id: int) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        payload = {"sub": str(user_id), "exp": expire, "type": "access"}
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def _create_refresh_token(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        ttl_seconds = settings.refresh_token_expire_days * 24 * 60 * 60
        redis_client.setex(f"{REFRESH_KEY_PREFIX}{token}", ttl_seconds, str(user_id))
        return token

    @staticmethod
    def create_oauth_state() -> str:
        state = str(uuid.uuid4())
        redis_client.setex(f"oauth_state:{state}", 600, "1")
        return state

    @staticmethod
    def verify_oauth_state(state: str) -> bool:
        key = f"oauth_state:{state}"
        if not redis_client.get(key):
            return False
        redis_client.delete(key)
        return True
