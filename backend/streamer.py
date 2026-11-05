"""Thin wrapper around the Snowpipe Streaming Python SDK."""

import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_RECOVERY_ATTEMPTS = 3
CHANNEL_COUNT = 2


class StreamingService:
    def __init__(
        self,
        account: str,
        user: str,
        private_key_path: str,
        database: str,
        schema: str,
        table: str,
        role: str | None = None,
    ):
        self.account = account
        self.user = user
        self.private_key_path = Path(private_key_path).expanduser().resolve()
        self.database = database
        self.schema = schema
        self.table = table
        self.pipe_name = f"{table}-STREAMING"
        self.role = role
        self.client = None
        self.channels: list = []
        self._lock = threading.Lock()
        self._recovering: set[int] = set()
        self._offset = 0

    def initialize(self):
        from snowflake.ingest.streaming import StreamingIngestClient

        private_key = self.private_key_path.read_text()
        profile: dict = {
            "account": self.account,
            "user": self.user,
            "url": f"https://{self.account}.snowflakecomputing.com:443",
            "private_key": private_key,
        }
        if self.role:
            profile["role"] = self.role

        profile_path = f"/tmp/profile_streaming_demo.json"
        with open(profile_path, "w") as f:
            json.dump(profile, f)

        self.client = StreamingIngestClient(
            client_name="security_cam_demo",
            db_name=self.database,
            schema_name=self.schema,
            pipe_name=self.pipe_name,
            profile_json=profile_path,
        )

        self.channels = []
        for i in range(CHANNEL_COUNT):
            ch, _ = self.client.open_channel(f"demo_ch_{i}")
            self.channels.append(ch)

        logger.info(f"StreamingService initialized: {CHANNEL_COUNT} channels → {self.database}.{self.schema}.{self.table}")

    def _partition(self, key: str) -> int:
        h = 0
        for c in key:
            h = ((h << 5) - h) + ord(c)
        return abs(h) % CHANNEL_COUNT

    def _is_recoverable(self, error: Exception) -> bool:
        msg = str(error).lower()
        return any(k in msg for k in ["token has expired", "invalid state", "invalidchannelerror", "unauthorized"])

    def _recover_channel(self, idx: int) -> bool:
        with self._lock:
            if idx in self._recovering:
                return False
            self._recovering.add(idx)
        try:
            try:
                self.channels[idx].close()
            except Exception:
                pass
            ch, _ = self.client.open_channel(f"demo_ch_{idx}")
            self.channels[idx] = ch
            return True
        except Exception as e:
            logger.error(f"Channel recovery failed for idx {idx}: {e}")
            return False
        finally:
            with self._lock:
                self._recovering.discard(idx)

    def append_row(self, row: dict, partition_key: str = "default") -> None:
        idx = self._partition(partition_key)
        offset = str(self._offset)
        self._offset += 1

        for attempt in range(MAX_RECOVERY_ATTEMPTS):
            try:
                self.channels[idx].append_row(row, offset_token=offset)
                return
            except Exception as e:
                if self._is_recoverable(e) and attempt < MAX_RECOVERY_ATTEMPTS - 1:
                    logger.warning(f"Channel error (attempt {attempt + 1}): {e} — recovering")
                    if self._recover_channel(idx):
                        continue
                raise

    def append_batch(self, rows: list[dict], partition_key: str = "default") -> None:
        """Send a batch of rows in a single SDK call — more efficient than one append_row per record."""
        idx = self._partition(partition_key)
        start = str(self._offset)
        end = str(self._offset + len(rows) - 1)
        self._offset += len(rows)

        for attempt in range(MAX_RECOVERY_ATTEMPTS):
            try:
                self.channels[idx].append_rows(rows, start_offset_token=start, end_offset_token=end)
                return
            except Exception as e:
                if self._is_recoverable(e) and attempt < MAX_RECOVERY_ATTEMPTS - 1:
                    logger.warning(f"Batch channel error (attempt {attempt + 1}): {e} — recovering")
                    if self._recover_channel(idx):
                        continue
                raise

    def shutdown(self):
        for ch in self.channels:
            try:
                ch.close()
            except Exception:
                pass
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        logger.info("StreamingService shut down")


def service_from_env() -> StreamingService:
    return StreamingService(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_path=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        table=os.environ["SNOWFLAKE_TABLE"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )
