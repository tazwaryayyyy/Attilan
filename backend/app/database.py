import asyncpg
from typing import AsyncGenerator, Optional
import uuid
from backend.app.config import settings


class DatabaseManager:
    """Manages async PostgreSQL connection pools with session state for Merkle triggers."""

    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=2,
                max_size=20,
            )

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def get_connection(
        self,
        actor_user_id: Optional[uuid.UUID] = None,
        client_ip: Optional[str] = None,
    ) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Yields an acquired database connection, setting session-scoped settings
        for Merkle audit ledger triggers.
        """
        if not self.pool:
            await self.connect()

        assert self.pool is not None
        async with self.pool.acquire() as conn:
            # Secure parameterized session variables (prevents SQL injection on session context)
            actor_str = str(actor_user_id) if actor_user_id else "00000000-0000-0000-0000-000000000000"
            ip_str = str(client_ip) if client_ip else "127.0.0.1"

            await conn.execute("SELECT set_config('opencase.actor_user_id', $1, false);", actor_str)
            await conn.execute("SELECT set_config('opencase.client_ip', $1, false);", ip_str)

            yield conn


db_manager = DatabaseManager()
