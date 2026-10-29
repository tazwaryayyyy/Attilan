# ATTILAN(1)

## NAME

`attilan` — controlled criminal-intelligence provenance ledger for Khulna deployments.

## ARCHITECTURE

```text
browser
  | TLS
nginx_gateway
  |-- /api --> fastapi_engine (api_worker transaction role)
  |-- /     --> frontend_ui (UID 10001)
  |
  +--> db_core
        |- db_owner             NOLOGIN: schema + trigger ownership
        |- api_worker           NOLOGIN: SELECT / INSERT / UPDATE only
        |- api_worker_login     LOGIN: SET LOCAL ROLE api_worker
        |- audit_reader         NOLOGIN: SELECT audit_merkle_ledger only
        `- audit_replica_login  LOGIN: SET ROLE audit_reader

fastapi_engine --> MinIO WORM object storage
hash_broadcaster --read-only--> Sequential Hash Chain Ledger --> remote checkpoint
```

## SECURITY BOUNDARIES

| Boundary | Limit |
| --- | --- |
| Cryptographic hashing | SHA-256 and BLAKE3 prove byte identity only; they do not establish truth. |
| Export output | Raw digest manifest only. No local certificate, X.509 signature, CA claim, or HSM fallback exists. |
| WORM object storage | Object Lock reduces deletion/overwrite capability; it is not an independent truth oracle. |
| Postgres RLS | JWT claims become `SET LOCAL app.current_actor_id` and clearance context for one transaction only. |
| Broadcaster | Separate read-only replica credential; SELECT is limited to `audit_merkle_ledger`. |
| Deployment | Production services use Docker bridge networking and target BDIX-hosted infrastructure. |

## LOCAL PROCEDURE

```sh
cp .env.example .env
# Replace every CHANGE_ME value with URL-safe random material before continuing.
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml build --pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
curl --fail --silent --show-error https://localhost/health
```

Issue a JWT through the authorized identity provider. It must contain a UUID `sub`, `exp`, `iat`, configured `iss`, configured `aud`, and an explicit `clearances` array.

```sh
curl --fail --silent --show-error \
  --header "Authorization: Bearer $ATTILAN_JWT" \
  "https://localhost/api/export/certificate/$SOURCE_UUID?format=markdown"
```

The endpoint returns `UNCERTIFIED_RAW_DIGEST_MANIFEST`. A Section 65B certification claim requires manual hardware-HSM workflow outside this repository.

## INTEGRITY CHECKS

```sh
python -m pip install --no-cache-dir -r backend/requirements.txt
$env:JWT_SECRET_KEY = 'ci-only-key'                 # PowerShell
$env:JWT_ISSUER = 'attilan-ci'
$env:JWT_AUDIENCE = 'attilan-ci-client'
$env:DATABASE_URL = 'postgresql://api_worker_login:ci_worker_password@localhost:5432/opencase_test'
pytest backend/tests -q
npm --prefix frontend ci
npm --prefix frontend run build
docker compose -f docker-compose.prod.yml config
```

## OPERATIONS

```sh
docker compose -f docker-compose.prod.yml logs --tail=100 fastapi_engine hash_broadcaster
docker compose -f docker-compose.prod.yml exec db_core \
  psql -U "$DB_BOOTSTRAP_USER" -d "$POSTGRES_DB" -c '\du api_worker audit_reader'
docker compose -f docker-compose.prod.yml exec db_core \
  psql -U "$DB_BOOTSTRAP_USER" -d "$POSTGRES_DB" -c '\dp audit_merkle_ledger'
```

## EXIT STATUS

`0` verified command completion. Any nonzero status means the requested boundary was not verified.
