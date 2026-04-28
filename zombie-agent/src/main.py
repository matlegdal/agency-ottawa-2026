"""FastAPI app entry point."""

import logging

from dotenv import load_dotenv

# Load .env BEFORE importing modules that read config.
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logging.getLogger("src.hooks").setLevel(logging.DEBUG)
logging.getLogger("src.agent").setLevel(logging.INFO)

from fastapi import FastAPI

from src.router import router


app = FastAPI(title="Zombie Recipients Agent", version="0.1.0")
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    from src.config import config

    uvicorn.run(
        "src.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
    )
