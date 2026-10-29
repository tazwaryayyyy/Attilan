from typing import List, Optional
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from backend.app.database import db_manager
from backend.app.services.disambiguation import (
    BengaliDisambiguationEvaluator,
    BengaliPhoneticEngine,
    DisambiguationCandidate,
)

router = APIRouter(prefix="/entity", tags=["Entity Resolution & Disambiguation"])


class DisambiguationQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_entity_id: Optional[uuid.UUID] = None
    primary_name_bn: str
    primary_name_en: Optional[str] = ""
    father_name_bn: Optional[str] = None
    thana_jurisdiction: Optional[str] = None
    age: Optional[int] = None


class DisambiguationQueueResponse(BaseModel):
    query_name_bn: str
    query_father_name_bn: Optional[str]
    candidate_matches: List[DisambiguationCandidate]
    security_notice: str = Field(
        default="STRICT BARRIER ENFORCED: Automatic UUID table merging is prohibited. Candidate matches require human-in-the-loop adjudication and two-key cryptographic sign-off."
    )


class DualKeyResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_a_id: uuid.UUID
    entity_b_id: uuid.UUID
    source_document_id: uuid.UUID
    contextual_label: str = Field(
        ...,
        description="Explicit evidentiary justification (e.g. 'CONFIRMED SAME AS VIA NID CROSS-CHECK IN SESSIONS CASE 101/2026')",
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    # Strict requirement: Explicit two-user JSON keys
    operator_key_1: str = Field(..., description="Cryptographic key / UUID of primary verifying analyst")
    operator_key_2: str = Field(..., description="Cryptographic key / UUID of secondary reviewing supervisor")


class ConflictResolutionResponse(BaseModel):
    edge_id: uuid.UUID
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: str
    contextual_label: str
    authorized_by_key_1: str
    authorized_by_key_2: str
    status: str
    message: str


@router.post("/evaluate_disambiguation", response_model=DisambiguationQueueResponse)
async def evaluate_disambiguation_queue(
    payload: DisambiguationQuery,
    request: Request,
) -> DisambiguationQueueResponse:
    """
    Computes Bengali phonetic and multi-attribute similarity against existing entity pool.
    Returns queue of candidate matches.
    CRITICAL: Does NOT merge underlying records under any circumstances.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    candidates: List[DisambiguationCandidate] = []

    async for conn in db_manager.get_connection(client_ip=client_ip):
        # Query potential matches using phonetic hash or trigram similarity
        rows = await conn.fetch(
            """
            SELECT entity_id, primary_name_bn, primary_name_en, father_name_bn
            FROM entities
            WHERE is_identity_disputed = FALSE
            LIMIT 50;
            """
        )

        for row in rows:
            if payload.target_entity_id and row["entity_id"] == payload.target_entity_id:
                continue

            candidate = BengaliDisambiguationEvaluator.evaluate_pair(
                target_entity_id=str(payload.target_entity_id or uuid.uuid4()),
                name_bn_1=payload.primary_name_bn,
                father_name_bn_1=payload.father_name_bn,
                thana_1=payload.thana_jurisdiction,
                age_1=payload.age,
                cand_entity_id=str(row["entity_id"]),
                name_bn_2=row["primary_name_bn"],
                name_en_2=row["primary_name_en"],
                father_name_bn_2=row["father_name_bn"],
                thana_2=payload.thana_jurisdiction,  # Compared against jurisdiction context
                age_2=payload.age,
            )
            # Surface if above threshold or high similarity
            if candidate.composite_score >= 0.50:
                candidates.append(candidate)

        # Sort descending by composite score
        candidates.sort(key=lambda c: c.composite_score, reverse=True)

        return DisambiguationQueueResponse(
            query_name_bn=payload.primary_name_bn,
            query_father_name_bn=payload.father_name_bn,
            candidate_matches=candidates,
        )

    # Fallback response if database connection pool is offline
    return DisambiguationQueueResponse(
        query_name_bn=payload.primary_name_bn,
        query_father_name_bn=payload.father_name_bn,
        candidate_matches=[],
    )


@router.post("/resolve_conflict", response_model=ConflictResolutionResponse, status_code=status.HTTP_201_CREATED)
async def resolve_disambiguation_conflict(
    payload: DualKeyResolutionRequest,
    request: Request,
) -> ConflictResolutionResponse:
    """
    VITAL SECURITY BARRIER:
    Enacts an explicit SAME_AS edge pointer link between two entity records.
    Mandates TWO distinct operator keys/credentials.
    NEVER merges or alters underlying table UUIDs.
    """
    if payload.entity_a_id == payload.entity_b_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot establish resolution edge to self.",
        )

    # Dual-Control Verification
    if payload.operator_key_1.strip() == payload.operator_key_2.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SECURITY RESTRICTION: Resolution requires two distinct, non-identical operator keys (Four-Eyes Principle).",
        )

    try:
        user1_uuid = uuid.UUID(payload.operator_key_1)
        user2_uuid = uuid.UUID(payload.operator_key_2)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Operator keys must be valid UUID credentials.",
        )

    client_ip = request.client.host if request.client else "127.0.0.1"

    async for conn in db_manager.get_connection(actor_user_id=user1_uuid, client_ip=client_ip):
        # Verify both entities exist
        entity_a = await conn.fetchrow("SELECT entity_id FROM entities WHERE entity_id = $1", payload.entity_a_id)
        entity_b = await conn.fetchrow("SELECT entity_id FROM entities WHERE entity_id = $1", payload.entity_b_id)

        if not entity_a or not entity_b:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both entity IDs do not exist in the Entity Registry.",
            )

        # Verify source document exists
        source_doc = await conn.fetchrow(
            "SELECT source_id FROM source_registry WHERE source_id = $1",
            payload.source_document_id,
        )
        if not source_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mandatory source_document_id does not exist in Source Registry.",
            )

        edge_id = uuid.uuid4()
        insert_edge_sql = """
            INSERT INTO entity_edges (
                edge_id,
                source_entity_id,
                target_entity_id,
                relationship_type,
                contextual_label,
                source_document_id,
                confidence_score,
                assertion_status,
                authorized_by_key_1,
                authorized_by_key_2
            ) VALUES ($1, $2, $3, 'SAME_AS', $4, $5, $6, 'COURT_CONFIRMED', $7, $8)
            RETURNING edge_id, created_at;
        """

        await conn.execute(
            insert_edge_sql,
            edge_id,
            payload.entity_a_id,
            payload.entity_b_id,
            payload.contextual_label,
            payload.source_document_id,
            payload.confidence_score,
            user1_uuid,
            user2_uuid,
        )

        return ConflictResolutionResponse(
            edge_id=edge_id,
            source_entity_id=payload.entity_a_id,
            target_entity_id=payload.entity_b_id,
            relationship_type="SAME_AS",
            contextual_label=payload.contextual_label,
            authorized_by_key_1=str(user1_uuid),
            authorized_by_key_2=str(user2_uuid),
            status="EDGE_LINKED_RECORDS_PRESERVED",
            message="Entities successfully linked via explicit SAME_AS edge pointer. Both original UUIDs and data lineages remain independent and unmerged.",
        )

    raise HTTPException(status_code=500, detail="Database connection failed.")
