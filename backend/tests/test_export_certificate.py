from datetime import date, datetime
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app


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

        async def mock_get_conn(*args, **kwargs):
            yield mock_conn

        mock_db_manager.get_connection = mock_get_conn

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/export/certificate/{source_id}")
            assert resp.status_code == 200
            data = resp.json()

            assert data["target_source_id"] == str(source_id)
            assert data["file_sha256"] == "a" * 64
            assert data["file_blake3"] == "b" * 64
            assert data["merkle_leaf_index"] == 42
            assert data["merkle_leaf_hash"] == "c" * 64
            assert "Section 65B(4)" in data["statutory_authority"]
            assert "uptime_duration" in data["system_operational_status"]
            assert data["x509_signature_block"]["signature_status"] == "CRYPTOGRAPHICALLY_SEALED"

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

        async def mock_get_conn(*args, **kwargs):
            yield mock_conn

        mock_db_manager.get_connection = mock_get_conn

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/export/certificate/{source_id}?format=markdown")
            assert resp.status_code == 200
            content = resp.text
            assert "CERTIFICATE OF DIGITAL EVIDENCE AUTHENTICITY" in content
            assert "Evidence (Amendment) Act 2022" in content
            assert "Primary Digest (SHA-256):" in content
            assert "e" * 64 in content
