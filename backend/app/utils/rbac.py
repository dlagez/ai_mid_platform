from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.utils.jwt import CurrentUser, get_current_user


async def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
