from contextlib import asynccontextmanager
from typing import AsyncGenerator, Iterable, Optional
import uuid
import json

import asyncpg
from backend.app.config import settings


class DatabaseManager:
    """Owns the bounded API pool and transaction-local RLS session context."""

    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        if self.pool:
            return
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is required; no database credential fallback is permitted")
        self.pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=20,
            command_timeout=30,
        )

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    @asynccontextmanager
    async def connection(
        self,
        *,
        actor_user_id: uuid.UUID,
        actor_clearances: Iterable[str],
        client_ip: Optional[str] = None,
    ) -> AsyncGenerator[asyncpg.Connection, None]:
        """Bind verified identity claims only for the lifetime of one transaction."""
        if not self.pool:
            await self.connect()

        assert self.pool is not None
        clearances = sorted({str(clearance) for clearance in actor_clearances})
        if not clearances:
            raise PermissionError("Authenticated principal has no authorization clearances")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # api_worker_login has no direct table grants. It may only assume the
                # NOLOGIN api_worker role for a transaction.
                await conn.execute("SET LOCAL ROLE api_worker")
                await conn.execute(
                    "SELECT set_config('app.current_actor_id', $1, true)",
                    str(actor_user_id),
                )
                await conn.execute(
                    "SELECT set_config('app.current_clearances', $1, true)",
                    json.dumps(clearances, separators=(",", ":")),
                )
                await conn.execute(
                    "SELECT set_config('app.client_ip', $1, true)",
                    str(client_ip or "0.0.0.0"),
                )
                yield conn


db_manager = DatabaseManager()
