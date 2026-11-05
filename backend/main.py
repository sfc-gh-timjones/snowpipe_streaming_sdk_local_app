"""FastAPI backend — Snowpipe Streaming demo for security camera events."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

import generator
from streamer import StreamingService, service_from_env

# Load .env from project root (one level up from backend/)
load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 250      # records per batch
BATCH_INTERVAL = 0.25  # seconds → 250 / 0.25 = 1000 records/sec to Snowflake
DISPLAY_EVERY_N = 50  # send 1 in 50 records to browser → ~20 display/sec, smooth UI

# Shared state
_service: StreamingService | None = None
_running = asyncio.Event()
_queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
_rows_sent_total: int = 0
_rows_sent_window: int = 0   # rows sent since last stats emit
_last_stats_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _service
    logger.info("Initializing Snowpipe Streaming client…")
    _service = service_from_env()
    await asyncio.to_thread(_service.initialize)
    logger.info("Ready.")
    yield
    logger.info("Shutting down…")
    _running.clear()
    if _service:
        await asyncio.to_thread(_service.shutdown)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _generation_loop():
    """Generate records, append to Snowflake via batch API, and push a sample to the SSE queue."""
    global _rows_sent_total, _rows_sent_window, _last_stats_time
    logger.info("Generation loop started (1000 rows/sec)")
    display_counter = 0
    _last_stats_time = asyncio.get_event_loop().time()
    while _running.is_set():
        batch = generator.make_batch(BATCH_SIZE)
        try:
            # One SDK call for the whole batch — much more efficient than per-row
            await asyncio.to_thread(_service.append_batch, batch)
            _rows_sent_total += BATCH_SIZE
            _rows_sent_window += BATCH_SIZE
        except Exception as e:
            logger.error(f"append_batch failed: {e}")
        for row in batch:
            display_counter += 1
            if display_counter % DISPLAY_EVERY_N == 0:
                try:
                    _queue.put_nowait(row)
                except asyncio.QueueFull:
                    pass
        # Emit a stats marker every second so the browser shows real Snowflake throughput
        now = asyncio.get_event_loop().time()
        elapsed = now - _last_stats_time
        if elapsed >= 1.0:
            rate = _rows_sent_window / elapsed
            _rows_sent_window = 0
            _last_stats_time = now
            try:
                _queue.put_nowait({"__stats__": True, "rows_per_sec": round(rate, 1), "total": _rows_sent_total})
            except asyncio.QueueFull:
                pass
        await asyncio.sleep(BATCH_INTERVAL)
    logger.info("Generation loop stopped")


@app.post("/start")
async def start():
    if not _running.is_set():
        _running.set()
        asyncio.create_task(_generation_loop())
        return {"status": "started"}
    return {"status": "already_running"}


@app.post("/stop")
async def stop():
    _running.clear()
    return {"status": "stopped"}


@app.get("/status")
async def status():
    return {"running": _running.is_set()}


@app.get("/stream")
async def stream():
    async def event_gen():
        while True:
            if not _running.is_set() and _queue.empty():
                yield {"event": "ping", "data": ""}
                await asyncio.sleep(1)
                continue
            try:
                row = await asyncio.wait_for(_queue.get(), timeout=1.0)
                if row.get("__stats__"):
                    yield {"event": "stats", "data": json.dumps({"rows_per_sec": row["rows_per_sec"], "total": row["total"]})}
                else:
                    yield {"data": json.dumps(row, default=str)}
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}

    return EventSourceResponse(event_gen())
