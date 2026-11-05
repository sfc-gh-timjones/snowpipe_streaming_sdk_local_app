# How This App Works — Explainer

A plain-language guide to what this demo does, how it's built, and how to explain it to someone watching.

---

## What it demonstrates

This app shows **Snowpipe Streaming (High-Performance Architecture)** — Snowflake's low-latency data ingestion service. It generates fake security camera events on your laptop and streams them directly into a Snowflake table in near real-time, with no staging, no COPY INTO, and no warehouse compute required for ingestion.

The point of the demo is: data is generated locally, it lands in Snowflake within a few seconds, and you can query it live in Snowsight while new rows are still arriving.

---

## What the app is built with

The app has two parts that run on your laptop simultaneously:

### Backend — Python (FastAPI)

The backend is a small Python web server written using **FastAPI**, a popular Python web framework. It does three things:

1. **Generates records** — a Python function creates realistic fake security camera events: camera ID, location, zone, event type (motion detected, person detected, intrusion alert, etc.), confidence score, and metadata. It generates 25 records at a time, 4 times per second, for a total of about 100 records per second.

2. **Streams to Snowflake** — it uses the **Snowpipe Streaming Python SDK** (`snowpipe-streaming` package from PyPI) to send those records directly to Snowflake. This is the core of the demo.

3. **Feeds the browser** — it sends a sample of the records (1 in 5, or 20/sec) to the browser UI via a technique called **Server-Sent Events (SSE)**, which is a live one-way data stream over HTTP.

### Frontend — React (Vite)

The browser UI is a **React** app served by **Vite**, a lightweight JavaScript build tool. It connects to the backend's live stream and displays incoming records in a scrolling feed — newest records at the top, capped at 200 visible at a time. It also shows real-time stats (rows/sec, total rows sent) that come directly from the backend.

---

## How Snowpipe Streaming works in this app

### Authentication

Snowpipe Streaming does not use username/password. It uses **RSA key-pair authentication**: a private key lives on your laptop, and the matching public key is registered on your Snowflake user. The SDK generates a short-lived signed token (JWT) from the private key to authenticate each request. This is why there's a key generation step in setup.

### The SDK

The Python SDK (`from snowflake.ingest.streaming import StreamingIngestClient`) is installed as a regular Python package. When the app starts, it:

1. Creates a **StreamingIngestClient** — this authenticates to Snowflake and establishes the streaming connection
2. Opens **2 channels** — a channel is an ordered, stateful stream of rows going into a specific table. Think of it as a dedicated pipeline. Multiple channels can write to the same table in parallel.

### Sending data

To send records, the app calls `channel.append_rows(batch)` — a single SDK call that sends a batch of 25 rows at once. The SDK:
- Serializes the rows
- Buffers them briefly in memory (~1 second default)
- Flushes them to Snowflake's streaming endpoint over HTTPS

No warehouse is used for ingestion. No S3/Azure/GCS staging bucket is involved. Rows go directly from the SDK to Snowflake's internal streaming layer.

### When do rows appear in Snowflake?

Two delays stack:

| Stage | Typical time | Controllable? |
|-------|-------------|---------------|
| Client-side buffer (SDK) | ~1 second | Yes — can call `initiate_flush()` to force immediate |
| Server-side processing (Snowflake) | ~3–5 seconds | No — this is Snowflake's internal pipeline |

**Total: roughly 4–6 seconds** from generation to being queryable. This is expected and normal for Snowpipe Streaming. It is not a sub-second system — it's designed for near-real-time use cases where seconds of latency is acceptable.

### Where does the data go?

Rows land in `STREAMING_DEMO.SECURITY.CAMERA_EVENTS`. The table was created in `setup.sql` with typed columns. The SDK maps Python dict keys to column names automatically — no transformation logic needed.

The `metadata` column is a `VARIANT` type in Snowflake, which stores JSON. The SDK receives a Python dict and stores it natively as an OBJECT (not a string), so you can query nested fields with Snowflake's dot-notation: `metadata:resolution`, `metadata:fps`, etc.

---

## What happens when you click "Generate Streaming Records"

1. Browser sends `POST /start` to the Python backend
2. Backend starts a background loop generating 25 records every 250ms
3. Each batch is sent to Snowflake via `channel.append_rows()`
4. 1 in 5 records is forwarded to the browser via SSE — you see them animate into the feed
5. Every second, the backend sends a stats update: actual rows/sec and total count
6. After ~4–6 seconds, the rows appear in Snowflake and `SELECT COUNT(*)` starts climbing

When you click Stop, the loop halts, the SDK flushes any buffered rows, and channels close cleanly.

---

## Key talking points

- **No warehouse for ingestion** — Snowpipe Streaming bypasses the warehouse entirely. You're not burning compute credits to load data.
- **No staging** — data doesn't touch S3 or any intermediate storage. It goes SDK → Snowflake directly.
- **Columnar from the start** — rows are ingested into a properly typed table, not dumped into a VARIANT catch-all.
- **Key-pair auth is required** — password auth isn't supported by the SDK. This is intentional for service-to-service security.
- **Channels are stateful** — the SDK tracks offsets (row sequence numbers) per channel. If a channel fails, it can be reopened and will resume from the last committed offset. This gives exactly-once delivery guarantees.
- **100 rows/sec is nothing** — the High-Performance Architecture is designed to handle millions of rows per second across many channels. This demo runs on a single laptop with 2 channels for illustration purposes.

---

## Common questions

**Why not just use a Kafka connector?**
You could. The Kafka connector also supports Snowpipe Streaming under the hood. This app skips Kafka because for simple streaming scenarios, the SDK is lighter — no broker infrastructure needed.

**Why Python and not Java?**
Both SDKs are fully supported. Python is faster to set up locally and more familiar for data practitioners. The Java SDK has the same capabilities.

**Is this the same as classic Snowpipe?**
No. Classic Snowpipe uses staged files (S3/GCS/Azure) and a COPY INTO pattern. High-Performance Snowpipe Streaming sends rows directly over an HTTP API — no files, no stage, lower latency, different billing model.

**What's the billing model?**
Snowpipe Streaming charges per GB ingested, not per credit/warehouse-second. There's no compute cost for the ingestion itself.
