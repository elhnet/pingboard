"""FastAPI application with background URL health checker."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

import checker
from db import get_all_urls, get_latest_checks, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop_event = asyncio.Event()
    task = asyncio.create_task(checker.run_checker(stop_event))
    yield
    stop_event.set()
    await task


app = FastAPI(title="Pingboard", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    urls = get_all_urls()
    results = []
    for url_row in urls:
        checks = get_latest_checks(url_row["id"], n=20)
        latest = None
        if checks:
            c = checks[0]
            latest = {
                "status_code": c["status_code"],
                "latency_ms": c["response_time_ms"],
                "ok": c["status_code"] is not None and 200 <= c["status_code"] < 400,
                "checked_at": c["checked_at"],
            }
        results.append({
            "url": url_row["url"],
            "latest": latest,
            "checks": [
                {
                    "status_code": c["status_code"],
                    "latency_ms": c["response_time_ms"],
                    "ok": c["status_code"] is not None and 200 <= c["status_code"] < 400,
                    "checked_at": c["checked_at"],
                }
                for c in checks
            ],
        })
    return results
