from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    INFLUX_URL: str
    INFLUX_TOKEN: str
    INFLUX_ORG: str
    INFLUX_BUCKET: str

    class Config:
        env_file = ".env"

settings = Settings()