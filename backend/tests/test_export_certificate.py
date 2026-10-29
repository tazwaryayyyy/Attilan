from datetime import date, datetime
from unittest.mock import AsyncMock, patch
import uuid
from contextlib import asynccontextmanager
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.tests.conftest import auth_headers


@pytest.mark.asyncio
class TestSection65BCertificateExport:
    """Verifies Evidence (Amendment) Act 2022 s.65B(4) certificate generation."""

    @patch("backend.app.routers.export.db_manager")
    async def test_generate_json_certificate(self, mock_db_manager):
        source_id = uuid.uuid4()
        now = datetime.now()

        mock_conn = AsyncMock()
        mock_conn.fetchrow.side_effect = [
            # source_row
            {
                "source_id": source_id,
                "source_type": "COURT_ORDER",
                "document_reference": "Sessions Case No. 12/2026",
                "issuing_authority": "Sessions Court Khulna",
                "publication_date": date(2026, 4, 15),
                "ingestion_timestamp": now,
                "storage_uri": "s3://opencase-evidence-worm/evidence/2026/test_order.pdf",
                "sha256_hash": "a" * 64,
                "blake3_hash": "b" * 64,
                "uploaded_by_user_id": uuid.uuid4(),
            },
            # merkle_row
            {
                "leaf_index": 42,
                "timestamp": now,
                "current_leaf_hash": "c" * 64,
                "preceding_leaf_hash": "0" * 64,
            },
        ]

        @asynccontextmanager
        async def mock_connection(**kwargs):
            yield mock_conn

        mock_db_manager.connection = mock_connection

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/export/certificate/{source_id}",
                headers=auth_headers(uuid.uuid4(), ["evidence:export"]),
            )
            assert resp.status_code == 200
            data = resp.json()

            assert data["target_source_id"] == str(source_id)
            assert data["file_sha256"] == "a" * 64
            assert data["file_blake3"] == "b" * 64
            assert data["sequential_hash_chain_index"] == 42
            assert data["sequential_hash_chain_hash"] == "c" * 64
            assert data["certification_status"] == "UNCERTIFIED_RAW_DIGEST_MANIFEST"
            assert data["manifest_sha256"]
            assert "CA HARDWARE X.509 MODULE UNAVAILABLE" in data["warnings"][0]

    @patch("backend.app.routers.export.db_manager")
    async def test_generate_markdown_certificate(self, mock_db_manager):
        source_id = uuid.uuid4()
        now = datetime.now()

        mock_conn = AsyncMock()
        mock_conn.fetchrow.side_effect = [
            {
                "source_id": source_id,
                "source_type": "POLICE_FIR",
                "document_reference": "Khulna Sadar PS FIR 08/2026",
                "issuing_authority": "KMP Khulna",
                "publication_date": date(2026, 3, 1),
                "ingestion_timestamp": now,
                "storage_uri": "s3://opencase-evidence-worm/evidence/2026/fir_08.pdf",
                "sha256_hash": "e" * 64,
                "blake3_hash": "f" * 64,
                "uploaded_by_user_id": uuid.uuid4(),
            },
            None,  # No merkle row yet
        ]

        @asynccontextmanager
        async def mock_connection(**kwargs):
            yield mock_conn

        mock_db_manager.connection = mock_connection

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/export/certificate/{source_id}?format=markdown",
                headers=auth_headers(uuid.uuid4(), ["evidence:export"]),
            )
            assert resp.status_code == 200
            content = resp.text
            assert "RAW DIGEST MANIFEST — UNCERTIFIED" in content
            assert "CA HARDWARE X.509 MODULE UNAVAILABLE" in content
            assert "File SHA-256:" in content
            assert "e" * 64 in content
