"""FastAPI application with background URL health checker."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

import checker


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    task = asyncio.create_task(checker.run_checker(stop_event))
    yield
    stop_event.set()
    await task


app = FastAPI(title="Pingboard", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}
