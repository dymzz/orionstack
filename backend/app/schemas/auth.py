from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str


class AuthStatusResponse(BaseModel):
    authenticated: bool
    username: str | None = None


class LogoutResponse(BaseModel):
    status: str
