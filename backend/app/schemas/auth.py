from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    login: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    login: str
    password: str


class UserOut(BaseModel):
    id: int
    login: str
    email: str | None

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
