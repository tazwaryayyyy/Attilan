from datetime import date, datetime
import io
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.database import db_manager
from backend.app.auth import AuthenticatedUser, require_clearance
from backend.app.services.hasher import CryptographicHasher
from backend.app.services.storage import storage_service

router = APIRouter(prefix="", tags=["Ingestion & Provenance"])


class IngestResponse(BaseModel):
    source_id: uuid.UUID
    source_type: str
    document_reference: str
    issuing_authority: str
    publication_date: date
    storage_uri: str
    sha256_hash: str
    blake3_hash: str
    file_size_bytes: int
    ingestion_timestamp: datetime
    uploaded_by_user_id: uuid.UUID
    evidentiary_note: str = Field(
        default="WORM Compliant. Cryptographically hashed via SHA-256 and BLAKE3. Sequential hash-chain ledger entry recorded."
    )


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_evidence_document(
    request: Request,
    file: UploadFile = File(..., description="Evidence file (PDF, TXT, or scan)"),
    source_type: str = Form(..., description="'COURT_ORDER', 'POLICE_FIR', 'GAZETTE', 'INVESTIGATIVE_REPORT'"),
    document_reference: str = Form(..., description="Official case number, gazette number, or memo ref"),
    issuing_authority: str = Form(..., description="Issuing body (e.g. 'Sessions Court Khulna', 'KMP Labanchora')"),
    publication_date: date = Form(..., description="Publication or issuance date"),
    source_signature: Optional[str] = Form(None, description="Hex/Base64 digital signature from source if present"),
    current_user: AuthenticatedUser = Depends(require_clearance("evidence:ingest")),
) -> IngestResponse:
    """
    Ingestion & Immutable Provenance Pipeline:
    1. Stream file bytes into memory buffer.
    2. Compute SHA-256 and BLAKE3 digests.
    3. Check `source_registry` for existing SHA-256 hash (strict anti-duplication).
    4. Store payload in MinIO WORM Object Lock storage bucket under COMPLIANCE retention mode.
    5. Commit record to PostgreSQL `source_registry` (trigger appends sequential hash-chain leaf).
    """
    valid_source_types = {"COURT_ORDER", "POLICE_FIR", "GAZETTE", "INVESTIGATIVE_REPORT"}
    if source_type.upper() not in valid_source_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid source_type '{source_type}'. Allowed: {sorted(list(valid_source_types))}",
        )

    # Read payload
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file payload is empty.",
        )

    buffer = io.BytesIO(content)

    # 1. Calculate dual cryptographic hashes
    sha256_hash, blake3_hash, file_size = CryptographicHasher.compute_stream_hashes(buffer)

    # Actor attribution is derived exclusively from the verified bearer token.
    actor_user_id = current_user.user_id

    client_ip = request.client.host if request.client else "127.0.0.1"

    source_sig_bytes = bytes.fromhex(source_signature) if source_signature else None

    # Database connection & existence check
    async with db_manager.connection(
        actor_user_id=actor_user_id,
        actor_clearances=current_user.clearances,
        client_ip=client_ip,
    ) as conn:
        # Check if identical hash has already been registered
        existing_row = await conn.fetchrow(
            "SELECT source_id, ingestion_timestamp, storage_uri FROM source_registry WHERE sha256_hash = $1",
            sha256_hash,
        )
        if existing_row:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Duplicate evidence detected. This exact document is already recorded.",
                    "existing_source_id": str(existing_row["source_id"]),
                    "ingestion_timestamp": existing_row["ingestion_timestamp"].isoformat(),
                    "storage_uri": existing_row["storage_uri"],
                    "sha256_hash": sha256_hash,
                },
            )

        # 2. Upload to MinIO WORM storage
        object_key = f"evidence/{publication_date.year}/{sha256_hash}_{file.filename}"
        content_type = file.content_type or "application/octet-stream"

        try:
            storage_uri = storage_service.upload_evidence(
                object_name=object_key,
                data_stream=buffer,
                length=file_size,
                content_type=content_type,
                metadata={
                    "source-type": source_type.upper(),
                    "sha256": sha256_hash,
                    "blake3": blake3_hash,
                    "document-reference": document_reference,
                },
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"WORM Storage failure during S3 compliance put: {str(err)}",
            )

        # 3. Insert into PostgreSQL source_registry (trigger appends sequential hash-chain leaf)
        source_id = uuid.uuid4()
        now = datetime.now()

        insert_sql = """
            INSERT INTO source_registry (
                source_id,
                source_type,
                document_reference,
                issuing_authority,
                publication_date,
                ingestion_timestamp,
                storage_uri,
                sha256_hash,
                blake3_hash,
                uploaded_by_user_id,
                source_signature
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING ingestion_timestamp;
        """

        record = await conn.fetchrow(
            insert_sql,
            source_id,
            source_type.upper(),
            document_reference,
            issuing_authority,
            publication_date,
            now,
            storage_uri,
            sha256_hash,
            blake3_hash,
            actor_user_id,
            source_sig_bytes,
        )

        ingestion_timestamp = record["ingestion_timestamp"]

        return IngestResponse(
            source_id=source_id,
            source_type=source_type.upper(),
            document_reference=document_reference,
            issuing_authority=issuing_authority,
            publication_date=publication_date,
            storage_uri=storage_uri,
            sha256_hash=sha256_hash,
            blake3_hash=blake3_hash,
            file_size_bytes=file_size,
            ingestion_timestamp=ingestion_timestamp,
            uploaded_by_user_id=actor_user_id,
        )

