from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.utils.jwt import CurrentUser, create_access_token, get_current_user
from configs.settings import settings

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUser


class MeResponse(BaseModel):
    user: CurrentUser
    permissions: list[str]


DEMO_USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin",
        "permissions": ["models:call", "tasks:read", "tasks:write", "knowledge:read", "knowledge:write"],
    },
    "operator": {
        "password": "operator123",
        "role": "operator",
        "permissions": ["models:call", "tasks:read", "tasks:write", "knowledge:read"],
    },
}


@router.post("/login", response_model=TokenResponse)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    user_record = DEMO_USERS.get(form_data.username)
    if not user_record or user_record["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = CurrentUser(
        username=form_data.username,
        role=user_record["role"],
        permissions=user_record["permissions"],
    )
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return TokenResponse(
        access_token=create_access_token(user.model_dump(), expires_delta=expires_delta),
        user=user,
    )


@router.get("/me", response_model=MeResponse)
async def me(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(user=current_user, permissions=current_user.permissions)
