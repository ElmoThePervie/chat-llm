from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.auth import RefreshRequest, TokenPair, UserCreate, UserLogin, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=TokenPair)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.register(data)
    return service.create_tokens(user)


@router.post("/login", response_model=TokenPair)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.login(data)
    return service.create_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.refresh_tokens(data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    AuthService(db).logout(data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/github")
def github_login():
    state = AuthService.create_oauth_state()
    params = urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
    )
    if not settings.github_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GitHub OAuth not configured")
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@router.get("/github/callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if not AuthService.verify_oauth_state(state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    service = AuthService(db)
    user = await service.github_callback(code)
    tokens = service.create_tokens(user)
    redirect_url = (
        f"{settings.frontend_url}/?access_token={tokens.access_token}"
        f"&refresh_token={tokens.refresh_token}"
    )
    return RedirectResponse(redirect_url)
