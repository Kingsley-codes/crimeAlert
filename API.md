# CrimeAlert API (`/api/v1`)

Every response is `{ "ok": true, "data": ... }` or `{ "ok": false, "error": { "message": "..." } }`.

| Endpoint | Auth | Body | Result |
|---|---|---|---|
| `POST /auth/login` | None | `email`, `password` | JWT access token and safe user profile |
| `POST /auth/logout` | Bearer token | none | Revokes the current token server-side |
| `POST /reports` | None | `crime_type`, `title`, `description`, `incident_datetime` (ISO-8601), `latitude`, `longitude`, optional `is_anonymous` | Pending anonymous report |
| `GET /reports` | None | optional `crime_type`, `risk_level`, `date_from`, `date_to`, `page`, `per_page` | Approved public reports only; location is rounded and reporter data is never included |
| `GET /reports/{id}` | None | none | One approved public report only |
| `GET /me/reports` | User bearer token | optional `page`, `per_page` | Current user's reports |
| `GET /me/reports/{id}` | User bearer token | none | A current-user report |
| `GET /notifications` | User/Admin bearer token | optional `unread=true` | Current user's notification history |
| `POST /notifications/{id}/read` | User/Admin bearer token | none | Marks only the current user's notification as read |
| `GET /admin/reports` | Admin bearer token | optional report filters, `page`, `per_page` | All reports, without reporter PII |
| `POST /admin/reports/{id}/approve` | Admin bearer token | none | Updated report |
| `POST /admin/reports/{id}/reject` | Admin bearer token | none | Updated report |
| `PATCH /admin/reports/{id}/classification` | Admin bearer token | `{ "crime_type": "theft" }` | Updated report |
| `PATCH /admin/reports/{id}/risk-level` | Admin bearer token | `{ "risk_level": "high" }` | Updated report |
| `GET /admin/map-analytics` | Admin bearer token | none | Report map data and top hotspot zones |
| `POST /admin/users/{id}/status` | Admin bearer token | `{ "action": "suspend" }` or `reactivate` | Updated account state |

List responses include `data.pagination` (`page`, `per_page`, `total`, `pages`). `per_page` is capped at 100. Bearer tokens are short-lived client credentials and logout adds their JWT ID to a persistent revocation blocklist. First-party browser calls may use their Flask-Login session, with CSRF validation enforced for state-changing API requests. Never place tokens in URLs or browser-local shared storage.
