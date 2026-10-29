-- OpenCase-BD: High-Assurance Criminal Intelligence & Evidence Integrity Platform
-- Stage 1: Database Initialization, Cryptographic Ledger, and Row-Level Security
-- Targeted Engine: PostgreSQL 17 + PostGIS + pgcrypto

\set ON_ERROR_STOP on

-- Enable Cryptographic, Geospatial, and Fuzzy Text Matching Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

--------------------------------------------------------------------------------
-- 0. Role boundaries and transaction context
--------------------------------------------------------------------------------
-- db_owner is a non-login ownership role. api_worker is deliberately NOLOGIN:
-- the API authenticates through api_worker_login and immediately SET LOCAL ROLE
-- api_worker inside a transaction. This prevents the network credential from
-- being a table-owning or superuser credential.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_owner') THEN
        CREATE ROLE db_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'api_worker') THEN
        CREATE ROLE api_worker NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'api_worker_login') THEN
        CREATE ROLE api_worker_login LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'audit_reader') THEN
        CREATE ROLE audit_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'audit_replica_login') THEN
        CREATE ROLE audit_replica_login LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END $$;

GRANT api_worker TO api_worker_login;
GRANT audit_reader TO audit_replica_login;

-- The entrypoint supplies these secrets only at initialization time. Refuse to
-- build roles with a baked-in or blank credential.
\getenv api_worker_password API_WORKER_PASSWORD
\getenv audit_replica_password AUDIT_REPLICA_PASSWORD
\if :{?api_worker_password}
\else
\quit 3
\endif
\if :{?audit_replica_password}
\else
\quit 3
\endif
SELECT format('ALTER ROLE api_worker_login PASSWORD %L', :'api_worker_password') \gexec
SELECT format('ALTER ROLE audit_replica_login PASSWORD %L', :'audit_replica_password') \gexec

CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION db_owner;

CREATE OR REPLACE FUNCTION app.current_actor_id()
RETURNS UUID
LANGUAGE SQL
STABLE
AS $$
    SELECT NULLIF(current_setting('app.current_actor_id', true), '')::UUID;
$$;

CREATE OR REPLACE FUNCTION app.has_clearance(required_clearance TEXT)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT COALESCE(current_setting('app.current_clearances', true), '[]')::JSONB ? required_clearance;
$$;

--------------------------------------------------------------------------------
-- 1. Epistemological Qualification Domain
--------------------------------------------------------------------------------
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'evidentiary_status') THEN
        CREATE TYPE evidentiary_status AS ENUM (
            'UNVERIFIED_INTELLIGENCE',
            'GD_REGISTERED',
            'FIR_COGNIZANCE',
            'SEIZURE_MANIFEST',
            'CHARGE_SHEET_ALLEGED',
            'JUDICIAL_CONVICTION',
            'JUDICIAL_ACQUITTAL'
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type_enum') THEN
        CREATE TYPE entity_type_enum AS ENUM (
            'INDIVIDUAL',
            'ORGANIZATION',
            'VEHICLE',
            'LOCATION',
            'WEAPON_NARCOTIC_SEIZURE'
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'relationship_type_enum') THEN
        CREATE TYPE relationship_type_enum AS ENUM (
            'ACCUSED_IN',
            'VICTIM_OF',
            'ASSOCIATE_OF',
            'CO_ACCUSED',
            'OWNER_OF',
            'LOCATED_AT',
            'MEMBER_OF',
            'SAME_AS'
        );
    END IF;
END $$;

--------------------------------------------------------------------------------
-- 2. Core Tables (res gotham.md Section 8.3 & Section 9)
--------------------------------------------------------------------------------

-- 2.1 Source Registry (Every single assertion must trace back here)
CREATE TABLE IF NOT EXISTS source_registry (
    source_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(64) NOT NULL, -- 'COURT_ORDER', 'POLICE_FIR', 'GAZETTE', 'INVESTIGATIVE_REPORT'
    document_reference VARCHAR(255) NOT NULL,
    issuing_authority VARCHAR(255) NOT NULL,
    publication_date DATE NOT NULL,
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    storage_uri VARCHAR(512) NOT NULL,
    sha256_hash CHAR(64) NOT NULL,
    blake3_hash CHAR(64) NOT NULL,
    uploaded_by_user_id UUID NOT NULL,
    source_signature BYTEA, -- Cryptographic provider signature if available
    CONSTRAINT unq_source_hash UNIQUE(sha256_hash)
);

-- 2.2 Documented Events (FIRs, GDs, Bail Hearings, Charge Sheets)
CREATE TABLE IF NOT EXISTS criminal_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_case_number VARCHAR(128), -- e.g., 'Khulna Sadar PS Case No. 12(05)2025'
    event_type VARCHAR(64) NOT NULL, -- 'FIR_REGISTRATION', 'BAIL_ORDER', 'CHARGE_SHEET'
    thana_jurisdiction VARCHAR(128) NOT NULL, -- e.g., 'Labanchora KMP', 'Rupsha District'
    district VARCHAR(64) NOT NULL DEFAULT 'Khulna',
    event_date DATE NOT NULL,
    location_geom GEOMETRY(Point, 4326),
    primary_source_id UUID NOT NULL REFERENCES source_registry(source_id),
    procedural_weight evidentiary_status NOT NULL,
    event_summary TEXT NOT NULL,
    is_superseded BOOLEAN NOT NULL DEFAULT FALSE,
    superseded_by_event_id UUID REFERENCES criminal_events(event_id),
    legal_justification TEXT -- Required court order citation when soft-tombstoning
);

-- 2.3 Entity Registry (Strictly Disambiguated)
CREATE TABLE IF NOT EXISTS entities (
    entity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type entity_type_enum NOT NULL DEFAULT 'INDIVIDUAL',
    primary_name_bn VARCHAR(255) NOT NULL,
    primary_name_en VARCHAR(255) NOT NULL,
    phonetic_hash_bn VARCHAR(64) NOT NULL, -- Bengali Soundex/Metaphone hash
    national_id_hash CHAR(64), -- SHA-256 of NID if lawfully available (NULL otherwise)
    father_name_bn VARCHAR(255),
    thana_jurisdiction VARCHAR(128),
    age SMALLINT CHECK (age IS NULL OR age BETWEEN 0 AND 130),
    disambiguation_confidence NUMERIC(5,2) NOT NULL DEFAULT 50.00,
    is_identity_disputed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Safe for initialization and for schema re-application to existing databases.
ALTER TABLE entities ADD COLUMN IF NOT EXISTS thana_jurisdiction VARCHAR(128);
ALTER TABLE entities ADD COLUMN IF NOT EXISTS age SMALLINT CHECK (age IS NULL OR age BETWEEN 0 AND 130);

-- 2.4 Provenance-Linked Assertions (The Edge: Connects Entity to Event)
CREATE TABLE IF NOT EXISTS event_assertions (
    assertion_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL REFERENCES criminal_events(event_id),
    entity_id UUID NOT NULL REFERENCES entities(entity_id),
    role_in_event VARCHAR(64) NOT NULL, -- 'ACCUSED', 'VICTIM', 'INFORMANT', 'IO', 'SURETY'
    status_at_event evidentiary_status NOT NULL,
    source_reference_page INT,
    source_quote_excerpt TEXT,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2.5 Entity Relationships (Explicit Graph Edges, including dual-key authenticated SAME_AS)
CREATE TABLE IF NOT EXISTS entity_edges (
    edge_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_entity_id UUID NOT NULL REFERENCES entities(entity_id),
    target_entity_id UUID NOT NULL REFERENCES entities(entity_id),
    relationship_type relationship_type_enum NOT NULL,
    contextual_label VARCHAR(255) NOT NULL, -- Strict literal label: 'CO-ACCUSED IN CHARGE SHEET NO. 04'
    source_document_id UUID NOT NULL REFERENCES source_registry(source_id),
    confidence_score NUMERIC(4,3) NOT NULL CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000),
    assertion_status VARCHAR(32) NOT NULL DEFAULT 'ALLEGED', -- 'ALLEGED', 'POLICE_CHARGED', 'COURT_CONFIRMED', 'DISPUTED'
    authorized_by_key_1 UUID NOT NULL,
    authorized_by_key_2 UUID, -- Required for SAME_AS disambiguation link
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_no_self_loop CHECK (source_entity_id <> target_entity_id)
);

-- 2.6 Append-Only Tamper-Evident Sequential Hash Chain Ledger
CREATE TABLE IF NOT EXISTS audit_merkle_ledger (
    leaf_index BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action_type VARCHAR(32) NOT NULL, -- 'INSERT', 'TOMBSTONE_UPDATE', 'DELETE_ATTEMPT', 'CORRECTION', 'EXPORT'
    target_table VARCHAR(64) NOT NULL,
    target_uuid UUID NOT NULL,
    actor_user_id UUID NOT NULL,
    client_ip INET NOT NULL,
    preceding_leaf_hash CHAR(64) NOT NULL,
    data_payload_hash CHAR(64) NOT NULL,
    current_leaf_hash CHAR(64) NOT NULL -- SHA256(leaf_index || timestamp || preceding_leaf_hash || data_payload_hash)
);

-- Performance & graph traversal indexes
CREATE INDEX IF NOT EXISTS idx_criminal_events_source ON criminal_events(primary_source_id);
CREATE INDEX IF NOT EXISTS idx_criminal_events_geom ON criminal_events USING GIST(location_geom);
CREATE INDEX IF NOT EXISTS idx_entities_trgm_bn ON entities USING GIN(primary_name_bn gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_entities_trgm_en ON entities USING GIN(primary_name_en gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_entities_phonetic ON entities(phonetic_hash_bn);
CREATE INDEX IF NOT EXISTS idx_event_assertions_entity ON event_assertions(entity_id);
CREATE INDEX IF NOT EXISTS idx_event_assertions_event ON event_assertions(event_id);
CREATE INDEX IF NOT EXISTS idx_entity_edges_source ON entity_edges(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_edges_target ON entity_edges(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_hash_chain_current_hash ON audit_merkle_ledger(current_leaf_hash);

--------------------------------------------------------------------------------
-- 3. Cryptographic Sequential Hash Chain Trigger Engine
--------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS hash_chain_mutex (
    id INT PRIMARY KEY DEFAULT 1,
    locked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
);
INSERT INTO hash_chain_mutex (id) VALUES (1) ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION process_sequential_hash_chain_event()
RETURNS TRIGGER AS $$
DECLARE
    v_prev_leaf_hash CHAR(64);
    v_payload_hash CHAR(64);
    v_action_type VARCHAR(32);
    v_target_uuid UUID;
    v_target_table VARCHAR(64);
    v_actor_user_id UUID;
    v_client_ip INET;
    v_payload_json JSONB;
    v_next_index BIGINT;
    v_now TIMESTAMPTZ;
    v_combined_payload TEXT;
    v_current_leaf_hash CHAR(64);
    v_genesis_hash CHAR(64) := '0000000000000000000000000000000000000000000000000000000000000000';
BEGIN
    v_target_table := TG_TABLE_NAME;
    v_now := clock_timestamp();

    -- The API sets these verified JWT claims with SET LOCAL. No anonymous audit
    -- attribution is allowed on the shared worker pool.
    v_actor_user_id := app.current_actor_id();
    IF v_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'RLS CONTEXT MISSING: app.current_actor_id is required.';
    END IF;

    BEGIN
        v_client_ip := NULLIF(current_setting('app.client_ip', true), '')::INET;
    EXCEPTION WHEN OTHERS THEN
        v_client_ip := NULL;
    END;
    IF v_client_ip IS NULL THEN
        v_client_ip := COALESCE(inet_client_addr(), '0.0.0.0'::INET);
    END IF;

    -- Determine Operation Type and Target UUID
    IF TG_OP = 'INSERT' THEN
        v_action_type := 'INSERT';
        v_payload_json := to_jsonb(NEW);
        
        IF v_target_table = 'source_registry' THEN v_target_uuid := NEW.source_id;
        ELSIF v_target_table = 'criminal_events' THEN v_target_uuid := NEW.event_id;
        ELSIF v_target_table = 'entities' THEN v_target_uuid := NEW.entity_id;
        ELSIF v_target_table = 'event_assertions' THEN v_target_uuid := NEW.assertion_id;
        ELSIF v_target_table = 'entity_edges' THEN v_target_uuid := NEW.edge_id;
        ELSE v_target_uuid := '00000000-0000-0000-0000-000000000000'::UUID;
        END IF;

    ELSIF TG_OP = 'UPDATE' THEN
        v_action_type := 'TOMBSTONE_UPDATE';
        v_payload_json := jsonb_build_object(
            'old', to_jsonb(OLD),
            'new', to_jsonb(NEW)
        );

        IF v_target_table = 'source_registry' THEN v_target_uuid := NEW.source_id;
        ELSIF v_target_table = 'criminal_events' THEN 
            v_target_uuid := NEW.event_id;
            IF NOT (NEW.is_superseded = TRUE AND NEW.legal_justification IS NOT NULL) THEN
                RAISE EXCEPTION 'PERMISSION DENIED: Direct UPDATE on criminal_events is prohibited. Soft-tombstone required (is_superseded=TRUE with valid legal_justification).';
            END IF;
        ELSIF v_target_table = 'entities' THEN v_target_uuid := NEW.entity_id;
        ELSIF v_target_table = 'event_assertions' THEN v_target_uuid := NEW.assertion_id;
        ELSIF v_target_table = 'entity_edges' THEN v_target_uuid := NEW.edge_id;
        ELSE v_target_uuid := '00000000-0000-0000-0000-000000000000'::UUID;
        END IF;
    END IF;

    -- Calculate SHA-256 Data Payload Hash
    v_payload_hash := encode(digest(v_payload_json::TEXT, 'sha256'), 'hex');

    -- Serialized chain hashing: lock the mutex to guarantee a linear sequence.
    PERFORM 1 FROM hash_chain_mutex WHERE id = 1 FOR UPDATE;

    -- Fetch latest leaf hash
    SELECT current_leaf_hash INTO v_prev_leaf_hash
    FROM audit_merkle_ledger
    ORDER BY leaf_index DESC
    LIMIT 1;

    IF v_prev_leaf_hash IS NULL THEN
        v_prev_leaf_hash := v_genesis_hash;
    END IF;

    -- Predict next sequence index
    v_next_index := nextval(pg_get_serial_sequence('audit_merkle_ledger', 'leaf_index'));

    -- Calculate Current Leaf Hash = SHA256(leaf_index || timestamp || preceding_leaf_hash || data_payload_hash)
    v_combined_payload := v_next_index::TEXT || v_now::TEXT || v_prev_leaf_hash || v_payload_hash;
    v_current_leaf_hash := encode(digest(v_combined_payload, 'sha256'), 'hex');

    -- Insert into immutable sequential hash-chain ledger
    INSERT INTO audit_merkle_ledger (
        leaf_index,
        timestamp,
        action_type,
        target_table,
        target_uuid,
        actor_user_id,
        client_ip,
        preceding_leaf_hash,
        data_payload_hash,
        current_leaf_hash
    ) VALUES (
        v_next_index,
        v_now,
        v_action_type,
        v_target_table,
        v_target_uuid,
        v_actor_user_id,
        v_client_ip,
        v_prev_leaf_hash,
        v_payload_hash,
        v_current_leaf_hash
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, app;

-- Attach sequential hash-chain triggers for insert and update.
DROP TRIGGER IF EXISTS trg_merkle_source_registry ON source_registry;
DROP TRIGGER IF EXISTS trg_hash_chain_source_registry ON source_registry;
CREATE TRIGGER trg_hash_chain_source_registry
    AFTER INSERT OR UPDATE ON source_registry
    FOR EACH ROW EXECUTE FUNCTION process_sequential_hash_chain_event();

DROP TRIGGER IF EXISTS trg_merkle_criminal_events ON criminal_events;
DROP TRIGGER IF EXISTS trg_hash_chain_criminal_events ON criminal_events;
CREATE TRIGGER trg_hash_chain_criminal_events
    AFTER INSERT OR UPDATE ON criminal_events
    FOR EACH ROW EXECUTE FUNCTION process_sequential_hash_chain_event();

DROP TRIGGER IF EXISTS trg_merkle_entities ON entities;
DROP TRIGGER IF EXISTS trg_hash_chain_entities ON entities;
CREATE TRIGGER trg_hash_chain_entities
    AFTER INSERT OR UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION process_sequential_hash_chain_event();

DROP TRIGGER IF EXISTS trg_merkle_event_assertions ON event_assertions;
DROP TRIGGER IF EXISTS trg_hash_chain_event_assertions ON event_assertions;
CREATE TRIGGER trg_hash_chain_event_assertions
    AFTER INSERT OR UPDATE ON event_assertions
    FOR EACH ROW EXECUTE FUNCTION process_sequential_hash_chain_event();

DROP TRIGGER IF EXISTS trg_merkle_entity_edges ON entity_edges;
DROP TRIGGER IF EXISTS trg_hash_chain_entity_edges ON entity_edges;
CREATE TRIGGER trg_hash_chain_entity_edges
    AFTER INSERT OR UPDATE ON entity_edges
    FOR EACH ROW EXECUTE FUNCTION process_sequential_hash_chain_event();

--------------------------------------------------------------------------------
-- 4. Native Hard-Delete Prevention Triggers (Section 16: RT-02)
--------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION enforce_criminal_events_soft_tombstone()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'EVIDENTIARY INTEGRITY VIOLATION: Hard DELETE on table criminal_events is prohibited by Section 9 Evidence Integrity Architecture. Soft-tombstone required (mutate is_superseded=TRUE with court justification).';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_soft_tombstone_criminal_events ON criminal_events;
CREATE TRIGGER trg_enforce_soft_tombstone_criminal_events
    BEFORE DELETE ON criminal_events
    FOR EACH ROW EXECUTE FUNCTION enforce_criminal_events_soft_tombstone();

CREATE OR REPLACE FUNCTION enforce_source_registry_delete_block()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'PERMISSION DENIED: Table source_registry is WORM-locked. Hard DELETE is prohibited.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_delete_block_source_registry ON source_registry;
CREATE TRIGGER trg_enforce_delete_block_source_registry
    BEFORE DELETE ON source_registry
    FOR EACH ROW EXECUTE FUNCTION enforce_source_registry_delete_block();

CREATE OR REPLACE FUNCTION protect_audit_ledger()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'PERMISSION DENIED: The audit_merkle_ledger is strictly append-only. Hard DELETE, UPDATE, or modification is prohibited.';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_protect_audit_ledger ON audit_merkle_ledger;
CREATE TRIGGER trg_protect_audit_ledger
    BEFORE UPDATE OR DELETE ON audit_merkle_ledger
    FOR EACH ROW EXECUTE FUNCTION protect_audit_ledger();

--------------------------------------------------------------------------------
-- 5. Native TRUNCATE Prevention Triggers (Section 16: RT-02)
--------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION block_table_truncate()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'PERMISSION DENIED: Table % is strictly append-only. Cannot truncate audit ledger or evidentiary records; TRUNCATE is prohibited under Evidence Integrity Architecture.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_block_truncate_merkle ON audit_merkle_ledger;
CREATE TRIGGER trg_block_truncate_merkle
    BEFORE TRUNCATE ON audit_merkle_ledger
    FOR EACH STATEMENT EXECUTE FUNCTION block_table_truncate();

DROP TRIGGER IF EXISTS trg_block_truncate_criminal_events ON criminal_events;
CREATE TRIGGER trg_block_truncate_criminal_events
    BEFORE TRUNCATE ON criminal_events
    FOR EACH STATEMENT EXECUTE FUNCTION block_table_truncate();

DROP TRIGGER IF EXISTS trg_block_truncate_source_registry ON source_registry;
CREATE TRIGGER trg_block_truncate_source_registry
    BEFORE TRUNCATE ON source_registry
    FOR EACH STATEMENT EXECUTE FUNCTION block_table_truncate();

--------------------------------------------------------------------------------
-- 6. Native DROP TABLE Event Trigger (Threat Tier 3: Rogue DBA Defense)
--------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION block_audit_drop_event()
RETURNS event_trigger AS $$
DECLARE
    obj record;
BEGIN
    FOR obj IN SELECT * FROM pg_event_trigger_dropped_objects()
    LOOP
        IF obj.object_name IN ('audit_merkle_ledger', 'criminal_events', 'source_registry', 'entities', 'event_assertions', 'entity_edges') THEN
            RAISE EXCEPTION 'PERMISSION DENIED: Dropping table % is prohibited by Section 9 Evidence Integrity Architecture.', obj.object_name;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

DROP EVENT TRIGGER IF EXISTS trg_block_audit_drop;
CREATE EVENT TRIGGER trg_block_audit_drop
    ON sql_drop
    EXECUTE FUNCTION block_audit_drop_event();

--------------------------------------------------------------------------------
-- 7. PostgreSQL Row-Level Security (RLS) & Permissions
--------------------------------------------------------------------------------

ALTER TABLE source_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE criminal_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_assertions ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_merkle_ledger ENABLE ROW LEVEL SECURITY;

-- Only the bounded workers receive table privileges. api_worker_login and
-- audit_replica_login have no direct grants; both must SET ROLE to a NOLOGIN
-- worker role. The API role cannot modify the ledger directly.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON TABLE audit_merkle_ledger FROM api_worker, audit_reader;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE audit_merkle_ledger FROM api_worker, audit_reader;
REVOKE DELETE, TRUNCATE ON source_registry, criminal_events, entities, event_assertions, entity_edges FROM api_worker;

GRANT USAGE ON SCHEMA public, app TO api_worker, audit_reader;
GRANT SELECT, INSERT, UPDATE ON source_registry, criminal_events, entities, event_assertions, entity_edges TO api_worker;
GRANT SELECT ON audit_merkle_ledger TO api_worker, audit_reader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO api_worker;
GRANT EXECUTE ON FUNCTION app.current_actor_id() TO api_worker;
GRANT EXECUTE ON FUNCTION app.has_clearance(TEXT) TO api_worker;

-- FORCE RLS so ownership cannot silently bypass policies on criminal data.
-- audit_merkle_ledger is excluded: SECURITY DEFINER hash-chain triggers must append as db_owner.
ALTER TABLE source_registry FORCE ROW LEVEL SECURITY;
ALTER TABLE criminal_events FORCE ROW LEVEL SECURITY;
ALTER TABLE entities FORCE ROW LEVEL SECURITY;
ALTER TABLE event_assertions FORCE ROW LEVEL SECURITY;
ALTER TABLE entity_edges FORCE ROW LEVEL SECURITY;

-- Every policy demands a verified JWT clearance that database.py copied into
-- SET LOCAL app.current_clearances for this transaction. The actor UUID is also
-- preserved for trigger attribution and source ownership.
DROP POLICY IF EXISTS source_read ON source_registry;
CREATE POLICY source_read ON source_registry FOR SELECT TO api_worker
    USING (app.has_clearance('evidence:read') OR app.has_clearance('evidence:export')
           OR app.has_clearance('criminal:write') OR app.has_clearance('entity:resolve'));
DROP POLICY IF EXISTS source_insert ON source_registry;
CREATE POLICY source_insert ON source_registry FOR INSERT TO api_worker
    WITH CHECK (app.has_clearance('evidence:ingest') AND uploaded_by_user_id = app.current_actor_id());
DROP POLICY IF EXISTS source_update ON source_registry;
CREATE POLICY source_update ON source_registry FOR UPDATE TO api_worker
    USING (app.has_clearance('evidence:write'))
    WITH CHECK (app.has_clearance('evidence:write'));

DROP POLICY IF EXISTS events_read ON criminal_events;
CREATE POLICY events_read ON criminal_events FOR SELECT TO api_worker
    USING (app.has_clearance('criminal:read') OR app.has_clearance('criminal:write'));
DROP POLICY IF EXISTS events_write ON criminal_events;
CREATE POLICY events_write ON criminal_events FOR INSERT TO api_worker
    WITH CHECK (app.has_clearance('criminal:write'));
DROP POLICY IF EXISTS events_update ON criminal_events;
CREATE POLICY events_update ON criminal_events FOR UPDATE TO api_worker
    USING (app.has_clearance('criminal:write'))
    WITH CHECK (app.has_clearance('criminal:write'));
DROP POLICY IF EXISTS rls_deny_delete_criminal_events ON criminal_events;
CREATE POLICY rls_deny_delete_criminal_events ON criminal_events FOR DELETE TO api_worker USING (false);

DROP POLICY IF EXISTS entities_read ON entities;
CREATE POLICY entities_read ON entities FOR SELECT TO api_worker
    USING (app.has_clearance('entity:read') OR app.has_clearance('entity:resolve'));
DROP POLICY IF EXISTS entities_write ON entities;
CREATE POLICY entities_write ON entities FOR INSERT TO api_worker
    WITH CHECK (app.has_clearance('entity:write'));
DROP POLICY IF EXISTS entities_update ON entities;
CREATE POLICY entities_update ON entities FOR UPDATE TO api_worker
    USING (app.has_clearance('entity:write'))
    WITH CHECK (app.has_clearance('entity:write'));

DROP POLICY IF EXISTS assertions_read ON event_assertions;
CREATE POLICY assertions_read ON event_assertions FOR SELECT TO api_worker
    USING (app.has_clearance('criminal:read') OR app.has_clearance('criminal:write'));
DROP POLICY IF EXISTS assertions_write ON event_assertions;
CREATE POLICY assertions_write ON event_assertions FOR INSERT TO api_worker
    WITH CHECK (app.has_clearance('criminal:write'));
DROP POLICY IF EXISTS assertions_update ON event_assertions;
CREATE POLICY assertions_update ON event_assertions FOR UPDATE TO api_worker
    USING (app.has_clearance('criminal:write'))
    WITH CHECK (app.has_clearance('criminal:write'));

DROP POLICY IF EXISTS edges_read ON entity_edges;
CREATE POLICY edges_read ON entity_edges FOR SELECT TO api_worker
    USING (app.has_clearance('entity:read') OR app.has_clearance('entity:resolve'));
DROP POLICY IF EXISTS edges_write ON entity_edges;
CREATE POLICY edges_write ON entity_edges FOR INSERT TO api_worker
    WITH CHECK (app.has_clearance('entity:resolve'));
DROP POLICY IF EXISTS edges_update ON entity_edges;
CREATE POLICY edges_update ON entity_edges FOR UPDATE TO api_worker
    USING (app.has_clearance('entity:resolve'))
    WITH CHECK (app.has_clearance('entity:resolve'));

DROP POLICY IF EXISTS ledger_api_read ON audit_merkle_ledger;
CREATE POLICY ledger_api_read ON audit_merkle_ledger FOR SELECT TO api_worker
    USING (app.has_clearance('audit:read') OR app.has_clearance('evidence:export'));
DROP POLICY IF EXISTS ledger_replica_read ON audit_merkle_ledger;
CREATE POLICY ledger_replica_read ON audit_merkle_ledger FOR SELECT TO audit_reader USING (true);
DROP POLICY IF EXISTS rls_deny_delete_merkle_ledger ON audit_merkle_ledger;
CREATE POLICY rls_deny_delete_merkle_ledger ON audit_merkle_ledger FOR DELETE TO api_worker, audit_reader USING (false);

-- Ownership exists only to run schema migrations and SECURITY DEFINER triggers;
-- db_owner cannot log in, so ownership does not create an application bypass.
ALTER TABLE source_registry OWNER TO db_owner;
ALTER TABLE criminal_events OWNER TO db_owner;
ALTER TABLE entities OWNER TO db_owner;
ALTER TABLE event_assertions OWNER TO db_owner;
ALTER TABLE entity_edges OWNER TO db_owner;
ALTER TABLE audit_merkle_ledger OWNER TO db_owner;
ALTER TABLE hash_chain_mutex OWNER TO db_owner;
ALTER SEQUENCE audit_merkle_ledger_leaf_index_seq OWNER TO db_owner;
ALTER FUNCTION app.current_actor_id() OWNER TO db_owner;
ALTER FUNCTION app.has_clearance(TEXT) OWNER TO db_owner;
ALTER FUNCTION process_sequential_hash_chain_event() OWNER TO db_owner;
ALTER FUNCTION enforce_criminal_events_soft_tombstone() OWNER TO db_owner;
ALTER FUNCTION enforce_source_registry_delete_block() OWNER TO db_owner;
ALTER FUNCTION protect_audit_ledger() OWNER TO db_owner;
ALTER FUNCTION block_table_truncate() OWNER TO db_owner;
