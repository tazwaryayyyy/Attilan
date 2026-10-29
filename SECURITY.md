# Security Policy & Evidentiary Assurance Architecture

## Scope and Principles

Attilan is engineered to process sensitive legal records, law enforcement filings, and public-interest evidentiary data within high-adversity jurisdictional environments. System security is governed by the statutory requirements of the **Evidence (Amendment) Act 2022 (Sections 65A & 65B)**, the **Cyber Security Act (CSA)**, and the **Personal Data Protection Act (PDPA)**.

---

## 1. Epistemic Limits of Cryptography

A foundational tenet of the Attilan security architecture is the clear division between **Data Integrity** and **Data Veracity**:

- **Data Integrity (Guaranteed)**: Mathematical proof via SHA-256 and BLAKE3 dual-hashing, S3 Compliance-Mode WORM locks, and append-only Merkle tree logs (`audit_merkle_ledger`) that a record has not been altered, superseded, or tampered with since the exact microsecond of intake.
- **Data Veracity (Not Guaranteed by Software)**: Cryptography cannot verify whether the human author of a First Information Report (FIR) or witness deposition spoke the truth. The platform enforces this epistemic boundary in the user interface and API layers by labeling all unadjudicated documents with statutory watermarks (`PRE-TRIAL ALLEGATION - NOT JUDICIALLY PROVEN`).

---

## 2. Adversarial Threat Model & Mitigations (Tabletop Threat Matrix)

The system is tested against active insider collusion, compromised credentials, and external denial-of-service vectors:

### RT-01: Fabricated Lawfare Ingestion
- **Threat**: Malicious actor feeds fabricated FIR numbers to manufacture criminal dossiers against political or commercial targets.
- **Safeguard**: District CMM/CJM registry cross-check token validation is enforced at API ingest (`/events/create`). Unverified claims are quarantined under the `UNVERIFIED_INTELLIGENCE` status and watermarked across all visual interfaces.

### RT-02: Rogue DBA Destructive Action
- **Threat**: A compromised superuser or corrupt database administrator connects directly to PostgreSQL and executes `TRUNCATE TABLE audit_merkle_ledger;` or `DROP TABLE criminal_events;` to erase an audit trail.
- **Safeguard**: Native C-level PostgreSQL `BEFORE TRUNCATE` triggers and `sql_drop` event triggers raise an unbypassable exception, rejecting table truncations and DDL drops regardless of superuser privileges.

### RT-04: False Identity Collision & Malicious Auto-Merge
- **Threat**: An adversary exploits Bengali phonetic similarities (e.g., "Md. Rafiqul Islam" vs. "Mohammad Rafiqul Islam") to merge a criminal record into an innocent citizen's profile.
- **Safeguard**: Silent background record merging is mathematically prohibited. Candidate matches require a 3-point deterministic score (Phonetics, Levenshtein, NID/case alignment) and mandate human-in-the-loop analyst approval. Merges create non-destructive `SAME_AS` edges without overwriting primary identity records.

### RT-09: Bulk Exfiltration & Data Scraping
- **Threat**: An attacker with analyst credentials attempts to bulk-export the criminal registry or witness identities.
- **Safeguard**: NGINX edge gateway enforces strict rate-limiting (`limit_req_zone`):
  - `/api/export`: Maximum 5 requests/minute.
  - `/api/events/create`: Maximum 20 requests/minute.
  - Excessive requests return `HTTP 429 Too Many Requests` and trigger security alerts.

### RT-10: Dual-Insider Collusion (Local Log Erasure)
- **Threat**: A system administrator and an investigative analyst conspire to simultaneously modify local database rows and reset local logs.
- **Safeguard**: The independent Merkle Broadcaster daemon (`merkle_broadcaster.py`) loops every 300 seconds, extracts sequential leaf hashes, signs them using HMAC-SHA256 (`APP_PRIVATE_SIGNING_KEY`), and dispatches them to an external, out-of-band HTTPS checkpoint. Any retrospective tampering creates an irreconcilable hash chain break.

---

## 3. Cryptographic and Transport Hardening

- **TLS Policy**: Edge proxy enforces strict **TLS 1.3 only** (`ssl_protocols TLSv1.3;`). Deprecated TLS 1.0, 1.1, and 1.2 handshakes are rejected.
- **HSTS**: `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` is asserted on every HTTPS response.
- **Object Storage**: MinIO S3 object locks are configured in **Compliance Mode** for 3,650 days. Objects cannot be overwritten, modified, or deleted even by the root administrator until the retention window elapses.

---

## 4. Reporting a Vulnerability

We welcome responsible security disclosures from the research community. If you discover a vulnerability in Attilan:

1. **Do not create a public GitHub issue.**
2. Send a PGP-encrypted report to the designated security response team at `security@attilan-defense.org`.
3. Include:
   - Vulnerability class and potential impact.
   - Proof of Concept (PoC) code or step-by-step reproduction instructions.
   - Affected service (`fastapi_engine`, `db_core`, `nginx_gateway`, `audit_broadcaster`).
4. We aim to acknowledge reports within 48 hours and provide a remediation timeline within 7 business days.

