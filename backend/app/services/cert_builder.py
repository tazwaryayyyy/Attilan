"""Unsigned mathematical digest manifests; certificate signing is intentionally absent."""

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Dict, Optional
import uuid

from blake3 import blake3
from pydantic import BaseModel, Field


CERT_STATUS_WARNING = (
    "[CERT-STATUS]: RAW DIGESTS GENERATED. CA HARDWARE X.509 MODULE UNAVAILABLE. "
    "AWAITING SECTION 65B MANUAL HARDWARE HSM KEY PLUG-IN."
)
logger = logging.getLogger("attilan.digest_manifest")


class RawDigestManifest(BaseModel):
    manifest_id: uuid.UUID
    generated_at_utc: str
    target_source_id: uuid.UUID
    requested_by_user_id: uuid.UUID
    document_reference: str
    issuing_authority: str
    publication_date: str
    storage_uri: str
    file_sha256: str
    file_blake3: str
    manifest_sha256: str
    manifest_blake3: str
    sequential_hash_chain_index: Optional[int]
    sequential_hash_chain_hash: Optional[str]
    certification_status: str = Field(default="UNCERTIFIED_RAW_DIGEST_MANIFEST")
    warnings: list[str]
    markdown_representation: str


class DigestManifestGenerator:
    """Produces only deterministic SHA-256 and BLAKE3 values over canonical data."""

    @staticmethod
    def _validate_digest(value: Any, label: str) -> str:
        normalized = str(value).lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError(f"{label} must be a 64-character hexadecimal digest")
        return normalized

    @classmethod
    def generate_manifest(
        cls,
        source_record: Dict[str, Any],
        ledger_record: Optional[Dict[str, Any]],
        requested_by: uuid.UUID,
    ) -> RawDigestManifest:
        # This visible warning is deliberately emitted for every manifest request;
        # it prevents consumers from mistaking a digest for a hardware-backed signature.
        print(CERT_STATUS_WARNING)
        logger.warning(CERT_STATUS_WARNING)

        file_sha256 = cls._validate_digest(source_record["sha256_hash"], "SHA-256")
        file_blake3 = cls._validate_digest(source_record["blake3_hash"], "BLAKE3")
        chain_index = ledger_record.get("leaf_index") if ledger_record else None
        chain_hash = ledger_record.get("current_leaf_hash") if ledger_record else None
        if chain_hash is not None:
            chain_hash = cls._validate_digest(chain_hash, "sequential hash-chain")

        canonical_payload = {
            "source_id": str(source_record["source_id"]),
            "sha256": file_sha256,
            "blake3": file_blake3,
            "sequential_hash_chain_index": chain_index,
            "sequential_hash_chain_hash": chain_hash,
        }
        canonical_bytes = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        manifest_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        manifest_blake3 = blake3(canonical_bytes).hexdigest()
        manifest_id = uuid.uuid4()
        generated_at = datetime.now(timezone.utc).isoformat()

        markdown = f"""# RAW DIGEST MANIFEST — UNCERTIFIED

{CERT_STATUS_WARNING}

- Manifest ID: `{manifest_id}`
- Generated (UTC): `{generated_at}`
- Source ID: `{source_record['source_id']}`
- Document reference: `{source_record['document_reference']}`
- Issuing authority: `{source_record['issuing_authority']}`
- Storage URI: `{source_record['storage_uri']}`
- File SHA-256: `{file_sha256}`
- File BLAKE3: `{file_blake3}`
- Sequential hash-chain index: `{chain_index if chain_index is not None else 'unavailable'}`
- Sequential hash-chain hash: `{chain_hash or 'unavailable'}`
- Canonical manifest SHA-256: `{manifest_sha256}`
- Canonical manifest BLAKE3: `{manifest_blake3}`

This output is a mathematical digest manifest only. It is not an X.509 certificate,
does not assert structural tamper detection, and requires manual hardware-HSM signing
before any Section 65B certification claim.
"""

        return RawDigestManifest(
            manifest_id=manifest_id,
            generated_at_utc=generated_at,
            target_source_id=source_record["source_id"],
            requested_by_user_id=requested_by,
            document_reference=source_record["document_reference"],
            issuing_authority=source_record["issuing_authority"],
            publication_date=str(source_record["publication_date"]),
            storage_uri=source_record["storage_uri"],
            file_sha256=file_sha256,
            file_blake3=file_blake3,
            manifest_sha256=manifest_sha256,
            manifest_blake3=manifest_blake3,
            sequential_hash_chain_index=chain_index,
            sequential_hash_chain_hash=chain_hash,
            warnings=[CERT_STATUS_WARNING],
            markdown_representation=markdown,
        )
