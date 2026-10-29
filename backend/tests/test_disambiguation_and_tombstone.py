import uuid
from datetime import date
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.app.services.disambiguation import (
    BengaliDisambiguationEvaluator,
    BengaliPhoneticEngine,
)


class TestBengaliDisambiguationEvaluator:
    """Tests phonetic normalization and composite disambiguation formula."""

    def test_honorific_and_unicode_normalization(self):
        norm1 = BengaliPhoneticEngine.normalize_text("Md.   Rafiqul Islam\u200c")
        norm2 = BengaliPhoneticEngine.normalize_text("mohammad rafiqul islam")
        norm_bn = BengaliPhoneticEngine.normalize_text("মোঃ রফিকুল ইসলাম\u200d")

        assert "mohammad" in norm1
        assert norm1 == norm2
        assert "মোহাম্মদ" in norm_bn

    def test_high_similarity_flags_human_adjudication(self):
        candidate = BengaliDisambiguationEvaluator.evaluate_pair(
            target_entity_id=str(uuid.uuid4()),
            name_bn_1="মোঃ রফিকুল ইসলাম",
            father_name_bn_1="আব্দুর রহমান",
            thana_1="labanchora",
            age_1=38,
            cand_entity_id=str(uuid.uuid4()),
            name_bn_2="মোহাম্মদ রফিকুল ইসলাম",
            name_en_2="Mohammad Rafiqul Islam",
            father_name_bn_2="আব্দুর রহমান",
            thana_2="labanchora",
            age_2=40,
        )

        assert candidate.composite_score >= 0.85
        assert candidate.adjudication_status == "FLAGGED FOR HUMAN ADJUDICATION"

    def test_low_similarity_treated_as_distinct_entity(self):
        candidate = BengaliDisambiguationEvaluator.evaluate_pair(
            target_entity_id=str(uuid.uuid4()),
            name_bn_1="মোঃ রফিকুল ইসলাম",
            father_name_bn_1="আব্দুর রহমান",
            thana_1="labanchora",
            age_1=38,
            cand_entity_id=str(uuid.uuid4()),
            name_bn_2="তারিকুল ইসলাম",
            name_en_2="Tariqul Islam",
            father_name_bn_2="সিরাজুল হক",
            thana_2="rupsha",
            age_2=25,
        )

        assert candidate.composite_score < 0.85
        assert "TREATED AS DISTINCT ENTITY" in candidate.adjudication_status


@pytest.mark.asyncio
class TestSecurityBarrierAndDualKeyResolution:
    """Verifies that conflict resolution mandates two distinct keys and never auto-merges."""

    @patch("backend.app.routers.entity.db_manager")
    async def test_single_user_key_rejection(self, mock_db_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            user_uuid = str(uuid.uuid4())
            payload = {
                "entity_a_id": str(uuid.uuid4()),
                "entity_b_id": str(uuid.uuid4()),
                "source_document_id": str(uuid.uuid4()),
                "contextual_label": "ATTEMPTED SINGLE USER MERGE",
                "confidence_score": 0.95,
                "operator_key_1": user_uuid,
                "operator_key_2": user_uuid,  # Identical key attempt
            }
            resp = await client.post("/entity/resolve_conflict", json=payload)
            assert resp.status_code == 403
            assert "Four-Eyes Principle" in resp.json()["detail"]

    @patch("backend.app.routers.entity.db_manager")
    async def test_dual_key_resolution_success(self, mock_db_manager):
        mock_conn = AsyncMock()
        mock_conn.fetchrow.side_effect = [
            {"entity_id": uuid.uuid4()},  # entity_a exists
            {"entity_id": uuid.uuid4()},  # entity_b exists
            {"source_id": uuid.uuid4()},  # source_doc exists
        ]
        mock_conn.execute.return_value = None

        async def mock_get_conn(*args, **kwargs):
            yield mock_conn

        mock_db_manager.get_connection = mock_get_conn

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "entity_a_id": str(uuid.uuid4()),
                "entity_b_id": str(uuid.uuid4()),
                "source_document_id": str(uuid.uuid4()),
                "contextual_label": "CONFIRMED SAME AS VIA NID CROSS-CHECK",
                "confidence_score": 0.95,
                "operator_key_1": str(uuid.uuid4()),
                "operator_key_2": str(uuid.uuid4()),  # Distinct secondary key
            }
            resp = await client.post("/entity/resolve_conflict", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["relationship_type"] == "SAME_AS"
            assert data["status"] == "EDGE_LINKED_RECORDS_PRESERVED"


@pytest.mark.asyncio
class TestSoftTombstoningController:
    """Verifies that events are soft-tombstoned and superseded with mandatory legal justification."""

    @patch("backend.app.routers.events.db_manager")
    async def test_successful_soft_tombstone(self, mock_db_manager):
        v1_event_id = uuid.uuid4()
        source_id = uuid.uuid4()

        from unittest.mock import MagicMock
        mock_conn = AsyncMock()
        tx_mock = MagicMock()
        tx_mock.__aenter__ = AsyncMock(return_value=None)
        tx_mock.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=tx_mock)

        # Mock V1 fetchrow: existing active event
        mock_conn.fetchrow.side_effect = [
            {
                "event_id": v1_event_id,
                "parent_case_number": "Khulna PS Case 12(05)2025",
                "thana_jurisdiction": "Labanchora KMP",
                "district": "Khulna",
                "procedural_weight": "CHARGE_SHEET_ALLEGED",
                "is_superseded": False,
            },
            {"source_id": source_id},  # Court source exists
        ]
        mock_conn.execute.return_value = None

        async def mock_get_conn(*args, **kwargs):
            yield mock_conn

        mock_db_manager.get_connection = mock_get_conn

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "legal_justification": "Certified Judgment: Sessions Case No. 45/2026, Accused Judicially Acquitted",
                "court_order_source_id": str(source_id),
                "new_event_type": "JUDICIAL_VERDICT",
                "new_procedural_weight": "JUDICIAL_ACQUITTAL",
                "new_event_summary": "Sessions Judge Court acquitted accused of all charges.",
                "new_event_date": "2026-06-15",
            }
            resp = await client.post(f"/events/{v1_event_id}/tombstone_and_supersede", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "MUTATED_TO_SUPERSEDED"
            assert data["active_procedural_weight"] == "JUDICIAL_ACQUITTAL"
            assert data["superseded_v1_event_id"] == str(v1_event_id)
            assert "historical v1 preserved" in data["message"].lower()
