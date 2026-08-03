from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = 'Fitness Business OS'
    debug: bool = False

    class Config:
        env_file = '.env'
