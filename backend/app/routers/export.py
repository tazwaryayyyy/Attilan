from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from backend.app.database import db_manager
from backend.app.auth import AuthenticatedUser, require_clearance
from backend.app.services.cert_builder import DigestManifestGenerator, RawDigestManifest

router = APIRouter(prefix="/export", tags=["Section 65B(4) Evidence Export Engine"])


@router.get("/certificate/{source_id}", response_model=RawDigestManifest)
async def generate_raw_digest_manifest(
    source_id: uuid.UUID,
    request: Request,
    format: Optional[str] = Query(default="json", description="'json' or 'markdown'"),
    current_user: AuthenticatedUser = Depends(require_clearance("evidence:export")),
):
    """
    Returns an unsigned raw-digest manifest. It is not a Section 65B certificate
    and contains no claim of CA/HSM signing or structural tamper verification.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    async with db_manager.connection(
        actor_user_id=current_user.user_id,
        actor_clearances=current_user.clearances,
        client_ip=client_ip,
    ) as conn:
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

        # 2. Fetch corresponding sequential hash-chain ledger entry.
        ledger_row = await conn.fetchrow(
            """
            SELECT leaf_index, timestamp, current_leaf_hash, preceding_leaf_hash
            FROM audit_merkle_ledger
            WHERE target_uuid = $1
            ORDER BY leaf_index ASC
            LIMIT 1;
            """,
            source_id,
        )

        manifest = DigestManifestGenerator.generate_manifest(
            source_record=dict(source_row),
            ledger_record=dict(ledger_row) if ledger_row else None,
            requested_by=current_user.user_id,
        )

        if format.lower() == "markdown":
            return PlainTextResponse(content=manifest.markdown_representation, media_type="text/markdown")

        return manifest
