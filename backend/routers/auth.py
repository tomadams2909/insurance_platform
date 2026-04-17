from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from auth.security import verify_password, create_access_token
from auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id)})
    tenant = user.tenant
    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant": {
            "name": tenant.name,
            "slug": tenant.slug,
            "primary_colour": tenant.primary_colour,
            "logo_url": tenant.logo_url,
            "favicon_url": tenant.favicon_url,
            "allowed_products": tenant.allowed_products,
        },
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role.value,
        "tenant_id": current_user.tenant_id,
    }
