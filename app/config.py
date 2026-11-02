from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./personas.db"
    LLM_API_KEY: str
    LLM_MODEL: str
    LLM_DELAY_SECONDS: float = 4.0
    
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
