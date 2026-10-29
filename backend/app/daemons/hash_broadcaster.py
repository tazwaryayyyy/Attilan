"""Read-only external broadcaster for the sequential hash-chain ledger."""

import asyncio
from datetime import datetime
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import signal
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [HashChainBroadcaster] %(message)s",
)
logger = logging.getLogger("attilan.hash_broadcaster")


class SequentialHashChainBroadcaster:
    """Broadcasts immutable chain leaves through a SELECT-only database role."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        signing_key: Optional[str] = None,
        remote_webhook_url: Optional[str] = None,
        cursor_file_path: Optional[str] = None,
        poll_interval_seconds: int = 300,
    ) -> None:
        self.database_url = database_url or os.getenv("AUDIT_REPLICA_DATABASE_URL", "")
        self.signing_key = signing_key or os.getenv("AUDIT_BROADCAST_HMAC_KEY", "")
        self.remote_webhook_url = remote_webhook_url or os.getenv("REMOTE_AUDIT_WEBHOOK_URL", "")
        self.cursor_file_path = Path(cursor_file_path or os.getenv("CURSOR_FILE_PATH", ".cursor"))
        self.poll_interval_seconds = int(os.getenv("BROADCAST_INTERVAL_SECONDS", str(poll_interval_seconds)))
        self._shutdown_event = asyncio.Event()

    def get_last_cursor(self) -> int:
        if not self.cursor_file_path.exists():
            return 0
        try:
            raw_text = self.cursor_file_path.read_text(encoding="utf-8").strip()
            return int(raw_text) if raw_text else 0
        except (OSError, ValueError) as exc:
            logger.warning("Cursor read failed; retaining a zero cursor: %s", exc)
            return 0

    def commit_cursor(self, last_index: int) -> None:
        self.cursor_file_path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.cursor_file_path.with_suffix(".tmp")
        pending.write_text(str(last_index), encoding="utf-8")
        pending.replace(self.cursor_file_path)

    def compute_hmac_signature(self, payload: bytes) -> str:
        return hmac.new(self.signing_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    async def fetch_unbroadcast_leaves(
        self, conn: asyncpg.Connection, cursor_value: int
    ) -> List[Dict[str, Any]]:
        # The login principal holds no grant. It may only SET LOCAL ROLE
        # audit_reader for the transaction; sole grant is SELECT on the ledger.
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE audit_reader")
            records = await conn.fetch(
                """
                SELECT leaf_index, timestamp, action_type, target_table, target_uuid,
                       actor_user_id, client_ip, preceding_leaf_hash, data_payload_hash,
                       current_leaf_hash
                FROM audit_merkle_ledger
                WHERE leaf_index > $1
                ORDER BY leaf_index ASC;
                """,
                cursor_value,
            )
        return [
            {
                "leaf_index": int(record["leaf_index"]),
                "timestamp": record["timestamp"].isoformat()
                if isinstance(record["timestamp"], datetime)
                else str(record["timestamp"]),
                "action_type": str(record["action_type"]),
                "target_table": str(record["target_table"]),
                "target_uuid": str(record["target_uuid"]),
                "actor_user_id": str(record["actor_user_id"]),
                "client_ip": str(record["client_ip"]),
                "preceding_leaf_hash": str(record["preceding_leaf_hash"]).strip(),
                "data_payload_hash": str(record["data_payload_hash"]).strip(),
                "current_leaf_hash": str(record["current_leaf_hash"]).strip(),
            }
            for record in records
        ]

    async def broadcast_batch(self, client: httpx.AsyncClient, batch: List[Dict[str, Any]]) -> bool:
        if not self.remote_webhook_url or not self.signing_key:
            logger.error("Read-only broadcaster is missing webhook URL or dedicated HMAC key.")
            return False
        payload = json.dumps(batch, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Audit-Signature-256": self.compute_hmac_signature(payload),
            "X-Audit-Batch-Count": str(len(batch)),
            "X-Audit-Min-Leaf-Index": str(batch[0]["leaf_index"]),
            "X-Audit-Max-Leaf-Index": str(batch[-1]["leaf_index"]),
            "User-Agent": "Attilan-Hash-Chain-Forwarder/1.0",
        }
        try:
            response = await client.post(self.remote_webhook_url, content=payload, headers=headers)
            if response.status_code in (200, 201):
                return True
            logger.error("External checkpoint rejected batch: HTTP %s", response.status_code)
        except httpx.HTTPError as exc:
            logger.error("External checkpoint transport failure: %s", exc)
        return False

    async def execute_broadcast_cycle(self, pool: asyncpg.Pool, client: httpx.AsyncClient) -> None:
        cursor = self.get_last_cursor()
        try:
            async with pool.acquire() as conn:
                leaves = await self.fetch_unbroadcast_leaves(conn, cursor)
            if not leaves:
                return
            if await self.broadcast_batch(client, leaves):
                self.commit_cursor(leaves[-1]["leaf_index"])
                logger.info("External checkpoint advanced to chain index %s.", leaves[-1]["leaf_index"])
            else:
                logger.warning("Checkpoint dispatch failed; cursor remains at %s.", cursor)
        except asyncpg.PostgresError as exc:
            logger.error("Read-only ledger query failed: %s", exc)

    async def run(self) -> None:
        if not self.database_url:
            raise RuntimeError("AUDIT_REPLICA_DATABASE_URL is required")
        pool: Optional[asyncpg.Pool] = None
        while not self._shutdown_event.is_set() and pool is None:
            try:
                pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=3, command_timeout=60)
            except (OSError, asyncpg.PostgresError) as exc:
                logger.error("Read-only replica connection failed: %s", exc)
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass
        if pool is None:
            return
        try:
            async with httpx.AsyncClient(timeout=30, verify=True) as client:
                while not self._shutdown_event.is_set():
                    await self.execute_broadcast_cycle(pool, client)
                    try:
                        await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.poll_interval_seconds)
                    except asyncio.TimeoutError:
                        pass
        finally:
            await pool.close()

    def stop(self) -> None:
        self._shutdown_event.set()


def main() -> None:
    daemon = SequentialHashChainBroadcaster()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def stop_handler(*_: Any) -> None:
        daemon.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_handler)
        except NotImplementedError:
            signal.signal(sig, stop_handler)
    try:
        loop.run_until_complete(daemon.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
