from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Fitness Business OS API")
    return app
