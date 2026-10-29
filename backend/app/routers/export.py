from typing import Optional
import uuid

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from backend.app.database import db_manager
from backend.app.services.cert_builder import CertificateGenerator, S65BCertificateModel

router = APIRouter(prefix="/export", tags=["Section 65B(4) Evidence Export Engine"])


@router.get("/certificate/{source_id}", response_model=S65BCertificateModel)
async def generate_section_65b_certificate(
    source_id: uuid.UUID,
    request: Request,
    format: Optional[str] = Query(default="json", description="'json' or 'markdown'"),
):
    """
    Evidence (Amendment) Act 2022, Section 65B(4) Certificate Builder:
    Extracts the immutable source record, database dual hashes (SHA-256 + BLAKE3),
    host server uptime metrics, Merkle ledger sequence leaf, and operator authorization.
    """
    actor_header = request.headers.get("X-Actor-User-Id")
    try:
        operator_uuid = uuid.UUID(actor_header) if actor_header else uuid.uuid4()
    except ValueError:
        operator_uuid = uuid.uuid4()

    client_ip = request.client.host if request.client else "127.0.0.1"

    async for conn in db_manager.get_connection(actor_user_id=operator_uuid, client_ip=client_ip):
        # 1. Fetch document from source_registry
        source_row = await conn.fetchrow(
            """
            SELECT source_id, source_type, document_reference, issuing_authority,
                   publication_date, ingestion_timestamp, storage_uri, sha256_hash,
                   blake3_hash, uploaded_by_user_id
            FROM source_registry
            WHERE source_id = $1;
            """,
            source_id,
        )

        if not source_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source record with ID '{source_id}' was not found in source_registry.",
            )

        # 2. Fetch corresponding Merkle audit ledger entry
        merkle_row = await conn.fetchrow(
            """
            SELECT leaf_index, timestamp, current_leaf_hash, preceding_leaf_hash
            FROM audit_merkle_ledger
            WHERE target_uuid = $1
            ORDER BY leaf_index ASC
            LIMIT 1;
            """,
            source_id,
        )

        cert = CertificateGenerator.generate_certificate(
            source_record=dict(source_row),
            merkle_record=dict(merkle_row) if merkle_row else None,
            operator_uuid=operator_uuid,
        )

        if format.lower() == "markdown":
            return PlainTextResponse(content=cert.markdown_representation, media_type="text/markdown")

        return cert

    raise HTTPException(status_code=500, detail="Database connection failed.")
