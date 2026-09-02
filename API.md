# CrimeAlert API (`/api/v1`)

Every response is `{ "ok": true, "data": ... }` or `{ "ok": false, "error": { "message": "..." } }`.

| Endpoint | Auth | Body | Result |
|---|---|---|---|
| `POST /auth/login` | None | `email`, `password` | JWT access token and safe user profile |
| `POST /auth/logout` | Bearer token | none | Client token-discard acknowledgement |
| `POST /reports` | None | `crime_type`, `title`, `description`, `incident_datetime` (ISO-8601), `latitude`, `longitude`, optional `is_anonymous` | Pending anonymous report |
| `GET /reports` | None | none | Approved public reports only; location is rounded and reporter data is never included |
| `GET /reports/{id}` | None | none | One approved public report only |
| `GET /me/reports` | User bearer token | none | Current user's reports |
| `GET /me/reports/{id}` | User bearer token | none | A current-user report |
| `GET /admin/reports` | Admin bearer token | none | All reports, without reporter PII |
| `POST /admin/reports/{id}/approve` | Admin bearer token | none | Updated report |
| `POST /admin/reports/{id}/reject` | Admin bearer token | none | Updated report |
| `PATCH /admin/reports/{id}/classification` | Admin bearer token | `{ "crime_type": "theft" }` | Updated report |
| `PATCH /admin/reports/{id}/risk-level` | Admin bearer token | `{ "risk_level": "high" }` | Updated report |

Bearer tokens are short-lived client credentials; browser sessions continue to use Flask-Login. Never place tokens in URLs or browser-local shared storage.
