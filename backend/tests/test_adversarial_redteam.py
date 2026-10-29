import os
import uuid
import hashlib
import logging
import pytest
import pytest_asyncio
import asyncpg
from difflib import SequenceMatcher
from httpx import ASGITransport, AsyncClient

# Imports pointing to OpenCase-BD Application Layers
from backend.app.main import app
from backend.app.services.disambiguation import (
    BengaliDisambiguationEvaluator,
    BengaliPhoneticEngine,
    commit_same_as_link,
)

# Core connection string to your test PostgreSQL 17 DB containing Stage 1 Schema.
# You must have your testing container active (e.g., POSTGRES_DB=opencase_test).
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgres://postgres:postgres@localhost:5432/opencase_test")


@pytest_asyncio.fixture(scope="function")
async def live_db_conn():
    """Establish a direct, low-level asyncpg connection mimicking DBA terminal access."""
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    yield conn
    await conn.close()


# ==============================================================================
# CLASS 1: TestRT01FabricatedLawfare (Section 16: RT-01)
# ==============================================================================
@pytest.mark.asyncio
class TestRT01FabricatedLawfare:
    """
    RT-01: Malicious user submits fabricated FIR alleging extortion/violence.
    The lack of a judicial_validation_token must mathematically mandate UNVERIFIED_ALLEGATION state.
    """
    async def test_unverified_lawfare_fir_quarantine(self, caplog):
        caplog.set_level(logging.WARNING)
        user_uuid = str(uuid.uuid4())
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"X-Actor-User-Id": user_uuid}
            payload = {
                "parent_case_number": "Khulna PS Case No. 99(09)2026",
                "event_type": "FIR_REGISTRATION",
                "thana_jurisdiction": "Labanchora KMP",
                "district": "Khulna",
                "event_date": "2026-09-15",
                "primary_source_id": str(uuid.uuid4()),
                "procedural_weight": "FIR_COGNIZANCE", # Attacker trying to spoof High-Level verification
                "event_summary": "Fabricated allegation of syndicate extortion against political rival.",
                "judicial_validation_token": None,  # The absent statutory token
            }
            
            resp = await client.post("/events/create", json=payload, headers=headers)
            assert resp.status_code == 201, f"Expected 201 Created but got {resp.status_code}"
            
            data = resp.json()
            
            # MANDATE 1: System MUST overwrite the attacker's attempted 'FIR_COGNIZANCE' state.
            assert data["procedural_weight"] == "UNVERIFIED_ALLEGATION", "FATAL: System accepted forged evidentiary weight."
            assert data["quarantined"] is True
            
            # MANDATE 2: Active incident tables must reject the payload ID
            assert data.get("active_event_id") is None
            
            # MANDATE 3: Threat Audit trailing MUST capture the precise actor UUID attempting lawfare
            assert user_uuid in caplog.text
            assert "SECURITY WARNING" in caplog.text


# ==============================================================================
# CLASS 2: TestRT02RogueDBADestructiveAction (Section 16: RT-02)
# ==============================================================================
@pytest.mark.asyncio
class TestRT02RogueDBADestructiveAction:
    """
    RT-02: LIVE EXECUTION TEST. A Rogue DBA / Threat Tier 3 executes raw SQL 
    to TRUNCATE the Merkle ledger or hard-delete events.
    This tests the Stage 1 DDL and RLS Database rules on the Postgres level, NOT MOCKS.
    """
    async def test_live_dba_truncate_audit_ledger_blocked(self, live_db_conn: asyncpg.Connection):
        """Attempts direct TRUNCATE via active driver. PostgreSQL Engine MUST block it."""
        with pytest.raises((asyncpg.exceptions.InsufficientPrivilegeError, asyncpg.exceptions.RaiseError)) as exc_info:
            # DIRECT TERMINAL EXECUTION: Rogue DBA Attempt
            await live_db_conn.execute("TRUNCATE TABLE audit_merkle_ledger CASCADE;")
        
        # We assert the exception originates strictly from PostgreSQL's C engine logic or Triggers
        error_msg = str(exc_info.value).lower()
        assert any(x in error_msg for x in ["permission denied", "prohibited", "cannot truncate", "append only"]), \
            f"FATAL SECURITY FAILURE: Postgres accepted a TRUNCATE command on the audit ledger. Output: {error_msg}"


    async def test_live_dba_hard_delete_criminal_events_blocked(self, live_db_conn: asyncpg.Connection):
        """Attempts direct DELETE on primary data table to verify cryptographic tombstone requirements."""
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()
        event_id = uuid.uuid4()
        sha256_dummy = hashlib.sha256(f"seed_rt02_{source_id}".encode("utf-8")).hexdigest()
        blake3_dummy = hashlib.sha256(f"seed_rt02_b3_{source_id}".encode("utf-8")).hexdigest()

        # Seed valid underlying DB records via live_db_conn
        await live_db_conn.execute(
            """
            INSERT INTO source_registry (
                source_id, source_type, document_reference, issuing_authority,
                publication_date, storage_uri, sha256_hash, blake3_hash, uploaded_by_user_id
            ) VALUES ($1, 'POLICE_FIR', 'REF-RT02-EVIDENCE', 'Labanchora Police Station', '2026-04-10', 's3://evidence/rt02.pdf', $2, $3, $4);
            """,
            source_id,
            sha256_dummy,
            blake3_dummy,
            user_id,
        )

        await live_db_conn.execute(
            """
            INSERT INTO criminal_events (
                event_id, parent_case_number, event_type, thana_jurisdiction,
                district, event_date, primary_source_id, procedural_weight, event_summary
            ) VALUES ($1, 'Khulna Sadar PS Case No. 44(04)2026', 'FIR_REGISTRATION', 'Labanchora KMP', 'Khulna', '2026-04-10', $2, 'FIR_COGNIZANCE', 'Seed event for hard-delete trigger verification');
            """,
            event_id,
            source_id,
        )

        with pytest.raises((asyncpg.exceptions.InsufficientPrivilegeError, asyncpg.exceptions.RaiseError)) as exc_info:
            await live_db_conn.execute("DELETE FROM criminal_events WHERE event_id = $1;", event_id)
            
        error_msg = str(exc_info.value).lower()
        assert any(x in error_msg for x in ["permission denied", "soft-tombstone required", "evidentiary integrity violation"]), \
            f"FATAL SECURITY FAILURE: System allowed hard data removal on criminal_events."


# ==============================================================================
# CLASS 3: TestRT03TransliterationCollision (Section 16: RT-03)
# ==============================================================================
@pytest.mark.asyncio
class TestRT03TransliterationCollision:
    """
    RT-03: System evaluates closely transliterated Bengali naming overlap.
    Logic enforces QUEUE evaluation ONLY to avoid mass data cross-contamination.
    """
    async def test_transliteration_collision_routing(self):
        name_1 = "Qazi Rashidul"
        name_2 = "Kazi Rashidul"
        
        # Phonetic Core Eval
        hash_1 = BengaliPhoneticEngine.generate_phonetic_hash(name_1)
        hash_2 = BengaliPhoneticEngine.generate_phonetic_hash(name_2)
        similarity = SequenceMatcher(None, hash_1, hash_2).ratio()
        
        assert similarity >= 0.80, f"Phonetic baseline engine failure. Expected >=0.80, got {similarity}"

        uuid_a = str(uuid.uuid4())
        uuid_b = str(uuid.uuid4())
        
        # Resolution Queue Processing
        candidate = BengaliDisambiguationEvaluator.evaluate_pair(
            target_entity_id=uuid_a,
            name_bn_1="কাজী রাশিদুল",
            father_name_bn_1="আব্দুল বারী",
            thana_1="Khulna Sadar",
            age_1=35,
            cand_entity_id=uuid_b,
            name_bn_2="কাজী রাশিদুল",
            name_en_2=name_2,
            father_name_bn_2="আব্দুল বারী",
            thana_2="Khulna Sadar",
            age_2=36,
        )

        # STRICT PROTOCOL: Auto merges are structurally impossible for human profiles
        assert candidate.action == "ROUTE_TO_QUEUE", "SYSTEM COMPROMISE: Failure to mandate human queue adjudication."
        assert candidate.action != "AUTO_MERGE"
        assert uuid_a != uuid_b, "CRITICAL DANGER: Variables internally crossed, distinct UUID tracking lost."


# ==============================================================================
# CLASS 4: TestRT04FalseIdentityMerge (Section 16: RT-04)
# ==============================================================================
@pytest.mark.asyncio
class TestRT04FalseIdentityMerge:
    """
    RT-04: Analyst tests matching individuals. The engine identifies explicit
    divergence tags ('thana', 'father_name_bn') blocking the candidate recommendation entirely.
    """
    async def test_divergent_identity_merge_blocked(self):
        candidate = BengaliDisambiguationEvaluator.evaluate_pair(
            target_entity_id=str(uuid.uuid4()),
            name_bn_1="মোঃ রফিকুল ইসলাম",
            father_name_bn_1="মরহুম আব্দুল আলী",
            thana_1="Khalishpur",
            age_1=42,
            cand_entity_id=str(uuid.uuid4()),
            name_bn_2="মোঃ রফিকুল ইসলাম",
            name_en_2="Md. Rafiqul Islam",
            father_name_bn_2="সিরাজুদ্দীন",
            thana_2="Sonadanga",
            age_2=31,
        )

        assert candidate.action == "BLOCKED_DIVERGENCE", "CRITICAL ERROR: Failed to block clearly distinct personal divergence flags."
        assert "father_name" in str(candidate.divergence_flags)

    async def test_manual_override_never_mutates_source_node(self, live_db_conn: asyncpg.Connection):
        """
        Final safety execution. Using active DB, verify manual merge commit_same_as_link
        constructs edge row tracking exclusively WITHOUT mutating original person table state.
        """
        e_uuid_1 = str(uuid.uuid4())
        e_uuid_2 = str(uuid.uuid4())
        source_doc = str(uuid.uuid4())
        user_uuid = str(uuid.uuid4())

        doc_sha = hashlib.sha256(f"seed_rt04_{source_doc}".encode("utf-8")).hexdigest()
        doc_blake = hashlib.sha256(f"seed_rt04_b3_{source_doc}".encode("utf-8")).hexdigest()

        # Seed requisite source document record
        await live_db_conn.execute(
            """
            INSERT INTO source_registry (
                source_id, source_type, document_reference, issuing_authority,
                publication_date, storage_uri, sha256_hash, blake3_hash, uploaded_by_user_id
            ) VALUES ($1, 'COURT_ORDER', 'CR-REVISION-2026-101', 'Khulna Sessions Court', '2026-05-18', 's3://evidence/rt04.pdf', $2, $3, $4);
            """,
            uuid.UUID(source_doc),
            doc_sha,
            doc_blake,
            uuid.UUID(user_uuid),
        )

        # Seed both target entities into entities table
        await live_db_conn.execute(
            """
            INSERT INTO entities (
                entity_id, entity_type, primary_name_bn, primary_name_en, phonetic_hash_bn
            ) VALUES 
                ($1, 'INDIVIDUAL', 'মোঃ রফিকুল ইসলাম', 'Md. Rafiqul Islam', 'R123'),
                ($2, 'INDIVIDUAL', 'রফিকুল ইসলাম', 'Rafiqul Islam', 'R123');
            """,
            uuid.UUID(e_uuid_1),
            uuid.UUID(e_uuid_2),
        )

        # Simulating Authorized multi-sig completion
        result = await commit_same_as_link(
            conn=live_db_conn, # Pass REAL live connection
            entity_a_id=e_uuid_1,
            entity_b_id=e_uuid_2,
            source_document_id=source_doc,
            operator_key_1="AUTHORIZER_IDEN_X",
            operator_key_2="VALIDATOR_IDEN_Y",
            contextual_label="MANUAL_MERGE_OFFICER_AUTHORIZED"
        )
        
        # Evidence assertion
        assert result["nodes_deleted"] == 0, "DATA TAMPERING OCCURRED: Engine purged independent entity history."
        assert result["relationship_type"] == "SAME_AS"
