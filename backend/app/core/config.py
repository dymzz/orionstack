from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "OrionStack API"
    app_env: str = "dev"
