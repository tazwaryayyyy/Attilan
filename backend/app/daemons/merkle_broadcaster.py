"""External Checkpoint Daemon (Syslog Broadcaster)

Architecture: res gotham.md - Stage D Evidence Integrity
Threat Model: RT-02 & RT-10 (Dual-Insider Collusion Audit Trail Tampering Defense)
Compliance: Evidence (Amendment) Act 2022 s.65B(4) Evidence Transparency
"""

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
import uuid

import asyncpg
import httpx

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MerkleBroadcaster] %(message)s",
)
logger = logging.getLogger("opencase.merkle_broadcaster")


class MerkleBroadcasterDaemon:
    """Asynchronous daemon broadcasting append-only Merkle ledger hashes to an external checkpoint."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        signing_key: Optional[str] = None,
        remote_webhook_url: Optional[str] = None,
        cursor_file_path: Optional[str] = None,
        poll_interval_seconds: int = 300,
    ) -> None:
        self.database_url: str = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@db_core:5432/opencase_bd",
        )
        self.signing_key: str = signing_key or os.getenv("APP_PRIVATE_SIGNING_KEY", "")
        self.remote_webhook_url: str = remote_webhook_url or os.getenv(
            "REMOTE_AUDIT_WEBHOOK_URL",
            "",
        )
        self.cursor_file_path: Path = Path(
            cursor_file_path or os.getenv("CURSOR_FILE_PATH", ".cursor")
        )
        self.poll_interval_seconds: int = int(
            os.getenv("BROADCAST_INTERVAL_SECONDS", str(poll_interval_seconds))
        )
        self._shutdown_event: asyncio.Event = asyncio.Event()

    def get_last_cursor(self) -> int:
        """Reads the highest successfully committed leaf_index from the local cursor file."""
        if not self.cursor_file_path.exists():
            return 0
        try:
            raw_text = self.cursor_file_path.read_text(encoding="utf-8").strip()
            return int(raw_text) if raw_text else 0
        except Exception as exc:
            logger.warning(
                f"Failed to read cursor file at {self.cursor_file_path} (defaulting to 0): {exc}"
            )
            return 0

    def commit_cursor(self, last_index: int) -> None:
        """Atomically commits the latest broadcast leaf_index to persistent storage."""
        self.cursor_file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.cursor_file_path.with_suffix(".tmp")
        tmp_path.write_text(str(last_index), encoding="utf-8")
        tmp_path.replace(self.cursor_file_path)

    def compute_hmac_signature(self, payload: bytes) -> str:
        """Computes HMAC-SHA256 signature across raw payload bytes using APP_PRIVATE_SIGNING_KEY."""
        return hmac.new(
            key=self.signing_key.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

    async def fetch_unbroadcast_leaves(
        self, conn: asyncpg.Connection, cursor_value: int
    ) -> List[Dict[str, Any]]:
        """Queries the append-only ledger for all leaf hashes created after the cursor."""
        query = """
            SELECT 
                leaf_index,
                timestamp,
                action_type,
                target_table,
                target_uuid,
                actor_user_id,
                client_ip,
                preceding_leaf_hash,
                data_payload_hash,
                current_leaf_hash
            FROM audit_merkle_ledger
            WHERE leaf_index > $1
            ORDER BY leaf_index ASC;
        """
        records = await conn.fetch(query, cursor_value)
        results: List[Dict[str, Any]] = []

        for r in records:
            results.append(
                {
                    "leaf_index": int(r["leaf_index"]),
                    "timestamp": r["timestamp"].isoformat()
                    if isinstance(r["timestamp"], datetime)
                    else str(r["timestamp"]),
                    "action_type": str(r["action_type"]),
                    "target_table": str(r["target_table"]),
                    "target_uuid": str(r["target_uuid"]),
                    "actor_user_id": str(r["actor_user_id"]),
                    "client_ip": str(r["client_ip"]),
                    "preceding_leaf_hash": str(r["preceding_leaf_hash"]).strip(),
                    "data_payload_hash": str(r["data_payload_hash"]).strip(),
                    "current_leaf_hash": str(r["current_leaf_hash"]).strip(),
                }
            )

        return results

    async def broadcast_batch(
        self, client: httpx.AsyncClient, batch: List[Dict[str, Any]]
    ) -> bool:
        """Serializes batch, computes cryptographic HMAC signature, and posts to remote webhook."""
        if not self.remote_webhook_url:
            logger.error("REMOTE_AUDIT_WEBHOOK_URL is not configured; skipping dispatch.")
            return False

        if not self.signing_key:
            logger.error("APP_PRIVATE_SIGNING_KEY is not configured; skipping dispatch.")
            return False

        payload_bytes = json.dumps(batch, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        signature = self.compute_hmac_signature(payload_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-Audit-Signature-256": signature,
            "X-Audit-Batch-Count": str(len(batch)),
            "X-Audit-Min-Leaf-Index": str(batch[0]["leaf_index"]),
            "X-Audit-Max-Leaf-Index": str(batch[-1]["leaf_index"]),
            "User-Agent": "Attilan-Merkle-Syslog-Forwarder/1.0",
        }

        try:
            response = await client.post(
                self.remote_webhook_url,
                content=payload_bytes,
                headers=headers,
            )
            if response.status_code in (200, 201):
                logger.info(
                    f"Successfully broadcast batch of {len(batch)} leaf hashes "
                    f"[{batch[0]['leaf_index']} -> {batch[-1]['leaf_index']}] "
                    f"to external checkpoint. HTTP {response.status_code}."
                )
                return True

            logger.error(
                f"External audit endpoint rejected checkpoint batch. "
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
            return False

        except httpx.TimeoutException:
            logger.error(
                f"Connection timeout transmitting batch to external checkpoint: {self.remote_webhook_url}"
            )
            return False
        except httpx.RequestError as exc:
            logger.error(
                f"Network/transport error communicating with external checkpoint: {exc}"
            )
            return False
        except Exception as exc:
            logger.error(f"Unexpected error broadcasting Merkle audit payload: {exc}")
            return False

    async def execute_broadcast_cycle(self, pool: asyncpg.Pool, http_client: httpx.AsyncClient) -> None:
        """Executes one polling and broadcast transaction."""
        current_cursor = self.get_last_cursor()

        try:
            async with pool.acquire() as conn:
                leaves = await self.fetch_unbroadcast_leaves(conn, current_cursor)

            if not leaves:
                logger.debug(f"Audit ledger up-to-date at leaf_index={current_cursor}. No new leaves.")
                return

            logger.info(
                f"Found {len(leaves)} unbroadcast Merkle leaves beyond cursor {current_cursor}."
            )

            success = await self.broadcast_batch(http_client, leaves)
            if success:
                new_max_index = leaves[-1]["leaf_index"]
                self.commit_cursor(new_max_index)
                logger.info(f"Cursor advanced successfully to leaf_index={new_max_index}.")
            else:
                logger.warning(
                    f"Broadcast failed; cursor preserved at {current_cursor} for retry in next interval."
                )

        except asyncpg.PostgresError as exc:
            logger.error(f"Database query error while fetching Merkle leaves: {exc}")
        except Exception as exc:
            logger.error(f"Unhandled error during broadcast cycle: {exc}")

    async def run(self) -> None:
        """Main service loop running every poll_interval_seconds."""
        logger.info(
            f"Starting Merkle External Checkpoint Daemon (Interval: {self.poll_interval_seconds}s, "
            f"Cursor: {self.cursor_file_path})"
        )

        pool: Optional[asyncpg.Pool] = None
        while not self._shutdown_event.is_set() and pool is None:
            try:
                pool = await asyncpg.create_pool(
                    dsn=self.database_url,
                    min_size=1,
                    max_size=3,
                    command_timeout=60,
                )
            except Exception as exc:
                logger.error(
                    f"Unable to connect to database at {self.database_url}. Retrying in 10s: {exc}"
                )
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    pass

        if not pool:
            return

        async with httpx.AsyncClient(timeout=30.0, verify=True) as http_client:
            while not self._shutdown_event.is_set():
                await self.execute_broadcast_cycle(pool, http_client)

                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=float(self.poll_interval_seconds),
                    )
                except asyncio.TimeoutError:
                    pass

        await pool.close()
        logger.info("Merkle External Checkpoint Daemon terminated cleanly.")

    def stop(self) -> None:
        """Signals daemon to stop gracefully."""
        self._shutdown_event.set()


def main() -> None:
    daemon = MerkleBroadcasterDaemon()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _handle_signal(*_: Any) -> None:
        logger.info("Termination signal received. Shutting down daemon...")
        daemon.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Signal handling on Windows platform
            signal.signal(sig, _handle_signal)

    try:
        loop.run_until_complete(daemon.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()

