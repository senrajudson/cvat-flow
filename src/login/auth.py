# auth.py
from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    username: str | None = Field(None, description="CVAT username")
    password: str = Field(..., description="CVAT password")
    email: EmailStr | None = Field(None, description="CVAT email")

    def identity_payload(self) -> dict:
        if self.email:
            return {"email": self.email, "password": self.password}
        if self.username:
            return {"username": self.username, "password": self.password}
        raise ValueError("Informe username ou email")
