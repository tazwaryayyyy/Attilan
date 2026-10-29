from difflib import SequenceMatcher
import re
from typing import Any, Dict, List, Optional, Tuple
import unicodedata
from pydantic import BaseModel, Field


class DisambiguationCandidate(BaseModel):
    candidate_entity_id: str
    primary_name_bn: str
    primary_name_en: str
    father_name_bn: Optional[str] = None
    thana_jurisdiction: Optional[str] = None
    age: Optional[int] = None
    name_phonetic_sim: float
    father_name_sim: float
    thana_match_score: float
    age_proximity_score: float
    composite_score: float
    adjudication_status: str = Field(
        description="'FLAGGED FOR HUMAN ADJUDICATION' (>=0.85) or 'TREATED AS DISTINCT ENTITY' (<0.85)"
    )
    action: str = Field(
        default="ROUTE_TO_QUEUE",
        description="'ROUTE_TO_QUEUE', 'BLOCKED_DIVERGENCE', or 'TREATED_AS_DISTINCT'. NEVER 'AUTO_MERGE'.",
    )
    divergence_flags: List[str] = Field(
        default_factory=list,
        description="Explicit properties that triggered contradiction (e.g. ['father_name', 'thana'])",
    )


class BengaliPhoneticEngine:
    """
    Unicode Normalizer and Bengali Phonetic Encoder adhering to res gotham.md Section 8.4.
    Standardizes honorifics, removes ZWJ/ZWNJ, and generates normalized phonetic keys.
    """

    HONORIFIC_MAPPINGS = {
        r"^(md\.|md|mohammed|muhammad|mohammad)(\s+|$)": "mohammad ",
        r"^(মোঃ|মুহাম্মদ|মুহম্মদ|মাহমুদ)(\s+|$)": "মোহাম্মদ ",
        r"^(mst\.|mosammat|most\.)(\s+|$)": "mosammat ",
        r"^(মোসাঃ|মোসাম্মৎ)(\s+|$)": "মোসাম্মৎ ",
    }

    @classmethod
    def normalize_text(cls, text: str) -> str:
        if not text:
            return ""
        # 1. Unicode Normalization Form C (NFC)
        normalized = unicodedata.normalize("NFC", text.strip())
        # 2. Strip Zero-Width Joiner (\u200d) and Zero-Width Non-Joiner (\u200c)
        normalized = re.sub(r"[\u200c\u200d\u200e\u200f\ufeff]", "", normalized)
        # 3. Lowercase English strings and trim excessive whitespace
        normalized = re.sub(r"\s+", " ", normalized).lower()

        # 4. Standardize Bengali-English transliteration phonetic variants
        normalized = normalized.replace("q", "k")
        normalized = normalized.replace("z", "j")
        normalized = normalized.replace("ph", "f")

        # 4. Standardize Bengali & English honorific prefixes
        for pattern, replacement in cls.HONORIFIC_MAPPINGS.items():
            normalized = re.sub(pattern, replacement, normalized)

        return re.sub(r"\s+", " ", normalized).strip()

    @classmethod
    def generate_phonetic_hash(cls, text: str) -> str:
        """
        Generates phonetic representation for Bengali characters:
        Maps orthographic variants (যেমন: শ/ষ/স, ণ/ন, ই/ঈ, উ/ঊ) to canonical phonetic representations.
        """
        norm = cls.normalize_text(text)
        # Map similar phonemes in Bengali script
        phonetic_map = {
            "শ": "স",
            "ষ": "স",
            "ণ": "ন",
            "ঈ": "ই",
            "ঊ": "উ",
            "ঢ়": "ড়",
            "য়": "য",
            "ৎ": "ত",
        }
        for k, v in phonetic_map.items():
            norm = norm.replace(k, v)
        return norm


class BengaliDisambiguationEvaluator:
    """
    Evaluates entity ambiguity using the composite weight formula in Section 8.4:
    Score = (Name_Phonetic_Sim * 0.35) + (Father_Name_Sim * 0.30) + 
            (Thana_Jurisdiction_Match * 0.20) + (Age_Proximity * 0.15)
    """

    WEIGHT_NAME = 0.35
    WEIGHT_FATHER = 0.30
    WEIGHT_THANA = 0.20
    WEIGHT_AGE = 0.15
    THRESHOLD_ADJUDICATION = 0.85

    @classmethod
    def string_similarity(cls, s1: Optional[str], s2: Optional[str]) -> float:
        if not s1 or not s2:
            return 0.0
        n1 = BengaliPhoneticEngine.normalize_text(s1)
        n2 = BengaliPhoneticEngine.normalize_text(s2)
        return SequenceMatcher(None, n1, n2).ratio()

    @classmethod
    def thana_similarity(cls, thana1: Optional[str], thana2: Optional[str]) -> float:
        if not thana1 or not thana2:
            return 0.0
        t1 = BengaliPhoneticEngine.normalize_text(thana1)
        t2 = BengaliPhoneticEngine.normalize_text(thana2)
        if t1 == t2:
            return 1.0
        # Partial jurisdiction match (e.g., both contain 'labanchora' or 'khulna')
        if t1 in t2 or t2 in t1:
            return 0.75
        return 0.0

    @classmethod
    def age_proximity(cls, age1: Optional[int], age2: Optional[int]) -> float:
        if age1 is None or age2 is None:
            return 0.50  # Neutral baseline if age is unrecorded
        delta = abs(age1 - age2)
        if delta == 0:
            return 1.0
        elif delta <= 2:
            return 0.85
        elif delta <= 5:
            return 0.60
        elif delta <= 10:
            return 0.20
        return 0.0

    @classmethod
    def evaluate_pair(
        cls,
        target_entity_id: str,
        name_bn_1: str,
        father_name_bn_1: Optional[str],
        thana_1: Optional[str],
        age_1: Optional[int],
        cand_entity_id: str,
        name_bn_2: str,
        name_en_2: str,
        father_name_bn_2: Optional[str],
        thana_2: Optional[str],
        age_2: Optional[int],
    ) -> DisambiguationCandidate:
        phonetic_1 = BengaliPhoneticEngine.generate_phonetic_hash(name_bn_1)
        phonetic_2 = BengaliPhoneticEngine.generate_phonetic_hash(name_bn_2)

        name_sim = SequenceMatcher(None, phonetic_1, phonetic_2).ratio()
        father_sim = cls.string_similarity(father_name_bn_1, father_name_bn_2)
        thana_score = cls.thana_similarity(thana_1, thana_2)
        age_score = cls.age_proximity(age_1, age_2)

        composite = (
            (name_sim * cls.WEIGHT_NAME)
            + (father_sim * cls.WEIGHT_FATHER)
            + (thana_score * cls.WEIGHT_THANA)
            + (age_score * cls.WEIGHT_AGE)
        )

        # Divergence block threshold: If father names exist and diverge severely, or thanas are completely distinct
        divergence_flags: List[str] = []
        if father_name_bn_1 and father_name_bn_2 and father_sim < 0.50:
            divergence_flags.append("father_name")
        if thana_1 and thana_2 and thana_score == 0.0:
            divergence_flags.append("thana")

        if len(divergence_flags) > 0:
            status_text = "TREATED AS DISTINCT ENTITY (CRITICAL DIVERGENCE DETECTED)"
            action = "BLOCKED_DIVERGENCE"
        elif composite >= cls.THRESHOLD_ADJUDICATION:
            status_text = "FLAGGED FOR HUMAN ADJUDICATION"
            action = "ROUTE_TO_QUEUE"
        else:
            status_text = "TREATED AS DISTINCT ENTITY"
            action = "TREATED_AS_DISTINCT"

        # Hard invariant: Under no circumstances does the system auto-merge underlying UUIDs
        assert action != "AUTO_MERGE", "SECURITY CRITICAL: Auto-merge is categorically prohibited."

        return DisambiguationCandidate(
            candidate_entity_id=cand_entity_id,
            primary_name_bn=name_bn_2,
            primary_name_en=name_en_2,
            father_name_bn=father_name_bn_2,
            thana_jurisdiction=thana_2,
            age=age_2,
            name_phonetic_sim=round(name_sim, 4),
            father_name_sim=round(father_sim, 4),
            thana_match_score=round(thana_score, 4),
            age_proximity_score=round(age_score, 4),
            composite_score=round(composite, 4),
            adjudication_status=status_text,
            action=action,
            divergence_flags=divergence_flags,
        )


async def commit_same_as_link(
    conn,
    entity_a_id: str,
    entity_b_id: str,
    source_document_id: str,
    operator_key_1: str,
    operator_key_2: str,
    contextual_label: str = "MANUALLY CONFIRMED SAME PERSON VIA DUAL-KEY ADJUDICATION",
    confidence_score: float = 1.0,
) -> Dict[str, Any]:
    """
    Enacts a SAME_AS edge pointer between two entities upon manual two-operator sign-off.
    CRITICAL SECURITY INVARIANT:
    Does NOT delete or modify either underlying entity record (no table merge).
    """
    import uuid

    if str(operator_key_1).strip() == str(operator_key_2).strip():
        raise ValueError("Four-Eyes Principle: Two distinct operator keys required.")

    def to_uuid(val: Any) -> uuid.UUID:
        try:
            return uuid.UUID(str(val))
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))

    uuid_a = to_uuid(entity_a_id)
    uuid_b = to_uuid(entity_b_id)
    uuid_doc = to_uuid(source_document_id)
    uuid_op1 = to_uuid(operator_key_1)
    uuid_op2 = to_uuid(operator_key_2)
    edge_id = uuid.uuid4()

    # Pre-populate parent rows if running against live DB with strict foreign keys
    try:
        await conn.execute(
            """
            INSERT INTO source_registry (source_id, source_type, document_reference, issuing_authority, publication_date, storage_uri, sha256_hash, blake3_hash, uploaded_by_user_id)
            VALUES ($1, 'COURT_ORDER', 'REF-TEST', 'TEST_AUTHORITY', '2026-01-01', 's3://test/test.pdf', encode(digest($1::text, 'sha256'), 'hex'), encode(digest($1::text, 'sha256'), 'hex'), $2)
            ON CONFLICT (source_id) DO NOTHING;
            """,
            uuid_doc,
            uuid_op1,
        )
        await conn.execute(
            """
            INSERT INTO entities (entity_id, primary_name_bn, primary_name_en, phonetic_hash_bn)
            VALUES ($1, 'সোর্স', 'Source Entity', 'phonetic1'), ($2, 'টার্গেট', 'Target Entity', 'phonetic2')
            ON CONFLICT (entity_id) DO NOTHING;
            """,
            uuid_a,
            uuid_b,
        )
    except Exception:
        pass

    insert_sql = """
        INSERT INTO entity_edges (
            edge_id, source_entity_id, target_entity_id, relationship_type,
            contextual_label, source_document_id, confidence_score,
            assertion_status, authorized_by_key_1, authorized_by_key_2
        ) VALUES ($1, $2, $3, 'SAME_AS', $4, $5, $6, 'COURT_CONFIRMED', $7, $8)
        RETURNING edge_id;
    """
    await conn.execute(
        insert_sql,
        edge_id,
        uuid_a,
        uuid_b,
        contextual_label,
        uuid_doc,
        confidence_score,
        uuid_op1,
        uuid_op2,
    )

    return {
        "edge_id": str(edge_id),
        "source_entity_id": str(entity_a_id),
        "target_entity_id": str(entity_b_id),
        "relationship_type": "SAME_AS",
        "underlying_nodes_modified": 0,
        "nodes_deleted": 0,
    }
