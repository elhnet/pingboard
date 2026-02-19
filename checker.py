"""Async background URL health checker."""

import asyncio
import json
import time
from pathlib import Path

import httpx

import db

CHECK_TIMEOUT = 5.0  # seconds


async def check_url(client: httpx.AsyncClient, url: str) -> dict:
    """Run a single HTTP GET and return status_code, ok, latency_ms, error."""
    try:
        start = time.monotonic()
        resp = await client.get(url, follow_redirects=True)
        latency_ms = (time.monotonic() - start) * 1000
        return {
            "status_code": resp.status_code,
            "ok": 200 <= resp.status_code < 400,
            "latency_ms": round(latency_ms, 2),
            "error": None,
        }
    except httpx.TimeoutException:
        return {
            "status_code": None,
            "ok": False,
            "latency_ms": None,
            "error": "timeout",
        }
    except httpx.ConnectError as exc:
        return {
            "status_code": None,
            "ok": False,
            "latency_ms": None,
            "error": f"connect_error: {exc}",
        }
    except httpx.HTTPError as exc:
        return {
            "status_code": None,
            "ok": False,
            "latency_ms": None,
            "error": str(exc),
        }


async def _check_loop(
    url_id: int,
    url: str,
    interval: int,
    client: httpx.AsyncClient,
    stop_event: asyncio.Event,
) -> None:
    """Check a single URL repeatedly at *interval* seconds until stopped."""
    while not stop_event.is_set():
        result = await check_url(client, url)
        db.record_check(
            url_id=url_id,
            status_code=result["status_code"],
            response_time_ms=result["latency_ms"],
            error=result["error"],
        )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass  # interval elapsed — loop again


async def run_checker(stop_event: asyncio.Event) -> None:
    """Main entry point: seed DB from urls.json, then check all URLs forever."""
    db.init_db()
    db.load_urls_from_json()

    urls = db.get_all_urls()
    if not urls:
        return

    async with httpx.AsyncClient(timeout=httpx.Timeout(CHECK_TIMEOUT)) as client:
        tasks = [
            asyncio.create_task(
                _check_loop(
                    url_id=row["id"],
                    url=row["url"],
                    interval=row["interval_seconds"],
                    client=client,
                    stop_event=stop_event,
                )
            )
            for row in urls
        ]
        # Wait until stop is signalled, then cancel all loops
        await stop_event.wait()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
