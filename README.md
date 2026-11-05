# Snowpipe Streaming SDK — Local Demo App

A small app on your laptop that generates fake security-camera events and streams them into a Snowflake table in real time, using the **Snowpipe Streaming Python SDK** (high-performance architecture). You click a button and watch rows land in Snowflake within seconds.

**Setup takes about 15 minutes.** Do the steps in order.

---

## What you need first

| Requirement | How to check | Where to get it |
| --- | --- | --- |
| A Snowflake account where you can use the `ACCOUNTADMIN` role | Log in to Snowsight | — |
| Python 3.10 or newer | `python3 --version` | https://www.python.org/downloads/ |
| Node.js 18 or newer | `node --version` | https://nodejs.org/ |
| Git | `git --version` | https://git-scm.com/downloads |
| OpenSSL (already installed on Mac/Linux) | `openssl version` | Windows: use Git Bash, which includes it |

> All commands below are for **Mac/Linux Terminal** or **Git Bash on Windows**.

---

## Step 1: Download the code

```bash
git clone https://github.com/sfc-gh-timjones/snowpipe_streaming_sdk_local_app.git
cd snowpipe_streaming_sdk_local_app
```

## Step 2: Create a key pair

The app logs in to Snowflake with a key file instead of a password. Run these four commands **exactly as written**:

```bash
mkdir -p ~/.snowflake/keys
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/keys/streaming_demo.p8 -nocrypt
openssl rsa -in ~/.snowflake/keys/streaming_demo.p8 -pubout -out ~/.snowflake/keys/streaming_demo.pub
chmod 600 ~/.snowflake/keys/streaming_demo.p8
```

Then print your **public** key as one line:

```bash
grep -v "^-" ~/.snowflake/keys/streaming_demo.pub | tr -d '\n'; echo
```

Copy the output (a long string starting with `MII...`). You need it in Step 3.

> The `.p8` file is your **private** key. Never share it or commit it to Git. It stays in your home folder, outside this project.

## Step 3: Set up Snowflake

1. Log in to **Snowsight** and open a new **SQL Worksheet**.
2. Open `setup.sql` from this project and paste its full contents into the worksheet.
3. Find `<PASTE_PUBLIC_KEY_HERE>` and replace it with the key you copied in Step 2. Keep the single quotes around it.
4. Click the dropdown next to **Run** and choose **Run All**.
5. The last result shows one value under `SNOWFLAKE_ACCOUNT` (for example `MYORG-MYACCOUNT`). **Copy it.** You need it in Step 4.

This creates the `STREAMING_DEMO` database, the `CAMERA_EVENTS` table, a `STREAMING_DEMO_ROLE` role, and a `STREAMING_DEMO_USER` service user.

## Step 4: Create your config file

```bash
cp .env.example .env
```

Open `.env` in any text editor and change **one line**: set `SNOWFLAKE_ACCOUNT` to the value you copied in Step 3.

```
SNOWFLAKE_ACCOUNT=MYORG-MYACCOUNT
```

Leave everything else as it is, then save the file.

## Step 5: Start the backend (Terminal window 1)

Open a terminal, `cd` into the project folder you cloned, then run:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --port 8000
```

<details>
<summary>Real-life example (Tim's machine)</summary>

```bash
cd /Users/timjones/projects/coco/Snowpipe_streaming_app/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8000
```
</details>

Wait until you see `Application startup complete`. **Leave this window open.**

## Step 6: Start the frontend (Terminal window 2)

Open a **second** terminal window, `cd` into the project folder you cloned, then run:

```bash
cd frontend
npm install
npm run dev
```

<details>
<summary>Real-life example (Tim's machine)</summary>

```bash
cd /Users/timjones/projects/coco/Snowpipe_streaming_app/frontend
npm install
npm run dev
```
</details>

**Leave this window open too.**

## Step 7: Run the demo

1. Open **http://localhost:5173** in your browser.
2. Click **Generate Streaming Records**.
3. In Snowsight, run this a few times and watch the count go up:

```sql
SELECT COUNT(*) FROM STREAMING_DEMO.SECURITY.CAMERA_EVENTS;
```

Done.

---

## Stopping and starting again

**Stop:** press `Ctrl+C` in both terminal windows.

**Start again later** (no reinstall needed):

Terminal 1 — from the project folder you cloned:
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --port 8000
```

Terminal 2 — from the project folder you cloned:
```bash
cd frontend
npm run dev
```

<details>
<summary>Real-life example (Tim's machine)</summary>

Terminal 1:
```bash
cd /Users/timjones/projects/coco/Snowpipe_streaming_app/backend
source .venv/bin/activate
uvicorn main:app --port 8000
```

Terminal 2:
```bash
cd /Users/timjones/projects/coco/Snowpipe_streaming_app/frontend
npm run dev
```
</details>

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `JWT token is invalid` or authentication error | The public key in Snowflake doesn't match your private key. Repeat Step 2, then in Snowsight run `ALTER USER STREAMING_DEMO_USER SET RSA_PUBLIC_KEY='<new key>';` |
| `Address already in use` on port 8000 | An old backend is still running. Mac/Linux: `lsof -ti:8000 \| xargs kill -9`, then start again. |
| Account or host not found | `SNOWFLAKE_ACCOUNT` in `.env` is wrong. Rerun the last `SELECT` in `setup.sql` and copy the value exactly. |
| `KeyError: 'SNOWFLAKE_ACCOUNT'` | The `.env` file is missing. Do Step 4 from the project's top folder, not inside `backend/`. |
| Browser page loads but nothing streams | Check that the backend window (Terminal 1) is still running and shows no errors. |
| `pip` install fails | Check `python3 --version` is 3.10 or newer. |

---

## More queries to try

```sql
-- Newest records
SELECT event_id, camera_id, event_type, confidence, ingested_at
FROM STREAMING_DEMO.SECURITY.CAMERA_EVENTS
ORDER BY ingested_at DESC LIMIT 20;

-- Events by type
SELECT event_type, COUNT(*) AS cnt
FROM STREAMING_DEMO.SECURITY.CAMERA_EVENTS
GROUP BY 1 ORDER BY 2 DESC;

-- Semi-structured metadata lands as a real OBJECT
SELECT metadata, TYPEOF(metadata) FROM STREAMING_DEMO.SECURITY.CAMERA_EVENTS LIMIT 1;
```

## Changing the speed

The default is **1,000 records/sec** (batches of 250 every 0.25 seconds). To change it, edit `BATCH_SIZE` in `backend/main.py`:

- 100/sec: `BATCH_SIZE = 25`
- 500/sec: `BATCH_SIZE = 125`
- 1,000/sec: `BATCH_SIZE = 250` (default)
- 2,000/sec: `BATCH_SIZE = 500`

The browser always shows ~20 rows/sec regardless of throughput (1 in every 50 is sampled to keep the UI smooth).

## Cleaning up

When you're finished, run the commented **Cleanup** section at the bottom of `setup.sql` in Snowsight. It drops the user, role, and database.

## How it works

See [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for the architecture.
