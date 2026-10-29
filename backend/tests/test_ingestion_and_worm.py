import io
from datetime import date
from contextlib import asynccontextmanager
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from minio.error import S3Error

from backend.app.services.hasher import CryptographicHasher
from backend.app.services.storage import MinioWORMStorage
from backend.tests.conftest import auth_headers


class TestCryptographicIntegrity:
    """Tests dual-hashing (SHA-256 and BLAKE3) and bit-level avalanche effect."""

    def test_hashing_consistency(self):
        sample_data = b"Case No. 12(05)2025: First Information Report recorded at Labanchora PS, Khulna."
        stream = io.BytesIO(sample_data)

        sha256_1, blake3_1, bytes_1 = CryptographicHasher.compute_stream_hashes(stream)
        sha256_2, blake3_2, bytes_2 = CryptographicHasher.compute_bytes_hashes(sample_data)

        assert sha256_1 == sha256_2
        assert blake3_1 == blake3_2
        assert bytes_1 == len(sample_data)
        assert len(sha256_1) == 64
        assert len(blake3_1) == 64

    def test_avalanche_effect_on_tampering(self):
        original_data = b"Charge Sheet 45/2026: Accused: Md. Tariqul Islam. Status: Accused."
        tampered_data = b"Charge Sheet 45/2026: Accused: Md. Tariqul Islam. Status: Cleared."

        orig_sha, orig_blake, _ = CryptographicHasher.compute_bytes_hashes(original_data)
        tamp_sha, tamp_blake, _ = CryptographicHasher.compute_bytes_hashes(tampered_data)

        assert orig_sha != tamp_sha
        assert orig_blake != tamp_blake


class TestWORMStorageCompliance:
    """
    Tests S3 WORM (Write Once, Read Many) compliance retention mode.
    Simulates attempts to overwrite or delete a locked object in MinIO.
    """

    def test_worm_overwrite_or_delete_rejection(self):
        storage = MinioWORMStorage()
        mock_minio = MagicMock()
        storage.client = mock_minio

        # Simulate S3 compliance error on delete attempt
        mock_minio.remove_object.side_effect = S3Error(
            code="AccessDenied",
            message="Object WORM locked: The specified object is protected under WORM compliance retention mode.",
            resource="opencase-evidence-worm/evidence/2026/test_fir.pdf",
            request_id="17E5E3D0A8B",
            host_id="minio1",
            response=None,
        )

        with pytest.raises(S3Error) as exc_info:
            storage.attempt_delete_object("evidence/2026/test_fir.pdf")

        assert exc_info.value.code == "AccessDenied"
        assert "WORM" in exc_info.value.message

    def test_worm_upload_sets_compliance_retention(self):
        storage = MinioWORMStorage()
        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True
        storage.client = mock_minio

        stream = io.BytesIO(b"Certified Court Copy - Sessions Judge Khulna")
        length = len(stream.getvalue())

        uri = storage.upload_evidence(
            object_name="evidence/2026/certified_order.pdf",
            data_stream=stream,
            length=length,
            content_type="application/pdf",
        )

        assert uri == f"s3://{storage.bucket_name}/evidence/2026/certified_order.pdf"
        assert mock_minio.put_object.called
        call_kwargs = mock_minio.put_object.call_args.kwargs
        retention = call_kwargs.get("retention")
        assert retention is not None
        assert retention.mode == "COMPLIANCE"


@pytest.mark.asyncio
class TestIngestAPIWorkflow:
    """Tests the /ingest route logic, dual hashing, and duplicate detection."""

    @patch("backend.app.routers.ingest.storage_service")
    @patch("backend.app.routers.ingest.db_manager")
    async def test_duplicate_ingestion_rejection(self, mock_db_manager, mock_storage):
        from httpx import ASGITransport, AsyncClient
        from backend.app.main import app
        from datetime import datetime

        # Mock DB connection returning an existing record with identical SHA-256
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "source_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "ingestion_timestamp": datetime(2026, 5, 12, 10, 0, 0),
            "storage_uri": "s3://opencase-evidence-worm/evidence/2026/sample.pdf",
        }

        @asynccontextmanager
        async def mock_connection(**kwargs):
            yield mock_conn

        mock_db_manager.connection = mock_connection

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("test.pdf", b"Identical File Content", "application/pdf")}
            data = {
                "source_type": "COURT_ORDER",
                "document_reference": "Khulna Sessions Case 101/2026",
                "issuing_authority": "Sessions Court, Khulna",
                "publication_date": "2026-05-12",
            }
            response = await client.post(
                "/ingest",
                files=files,
                data=data,
                headers=auth_headers(uuid.uuid4(), ["evidence:ingest"]),
            )

            assert response.status_code == 409
            json_resp = response.json()
            assert "Duplicate evidence detected" in json_resp["detail"]["message"]
