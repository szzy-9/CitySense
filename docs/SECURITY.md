# CitySense security

CitySense uses a small set of controls appropriate for an expo demo. This is
not a general-purpose user authentication system.

| Threat/control | Current implementation | Configuration | Verification | Remaining limitation |
| --- | --- | --- | --- | --- |
| HTTPS/TLS | Render terminates HTTPS. Production Flask responses include `Strict-Transport-Security: max-age=31536000`; Flask does not implement another redirect. | `FLASK_ENV=production` | `backend/tests/test_security.py` checks HSTS and local omission. | HSTS depends on deploying through HTTPS and setting the production environment correctly. |
| Demo access | Flask protects `/`, SPA paths, and application APIs with one shared password. `/login`, `/api/health`, and frontend static assets remain public. Werkzeug verifies only a stored password hash. | `ENABLE_DEMO_AUTH`, `DEMO_ACCESS_PASSWORD_HASH` | Tests cover redirects, API rejection, correct and incorrect passwords, and public health. | Shared access has no user identity, registration, recovery, MFA, lockout, or rate limiting. |
| Secure cookies | A signed Flask session stores only `demo_authenticated=true`. Production cookies are Secure, HttpOnly, and SameSite=Lax. | `SESSION_SECRET_KEY`, `FLASK_ENV=production` | Cookie flags and session contents are tested. | Sessions are shared-demo sessions rather than revocable per-user server-side records. |
| CORS | API CORS uses an explicit comma-separated origin allowlist; wildcard access is not enabled. | Render `ALLOWED_ORIGINS` must be the real deployed HTTPS origin. | Existing and new backend tests check allowed and rejected origins. | A changed deployment hostname requires a manual Render update. |
| CSP and headers | CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy` are added to responses. | `backend/app.py` | Regression tests check CSP and the principal headers. | CSP permits inline styles for the existing interface. |
| Input validation | Flask validates locations, search length, crowd tolerance, departure time, and monitoring geometry. | Backend service validation functions | Existing API and service tests cover invalid inputs. | Validation is scoped to current endpoints, not a general web application firewall. |
| Request size | Flask rejects request bodies larger than 64 KiB. | `Config.MAX_CONTENT_LENGTH` | `backend/tests/test_security.py` checks the 413 response. | This is an application limit, not traffic-rate protection. |
| Secret management | API keys, database credentials, password hashes, and session secrets come from ignored local environment files or Render environment variables. They are not returned by APIs. | Root `.env` locally; Render environment in production | Security tests use fake values and assert responses do not expose them. `.gitignore` excludes `.env` files. | Render project access still needs appropriate team permissions. |
| PostgreSQL TLS | `DATABASE_URL` is normalized for psycopg and defaults PostgreSQL connections to `sslmode=require`. The browser never receives database credentials or connects to Neon. | Render `DATABASE_URL` | `backend/tests/test_config.py` checks URL normalization and TLS mode. | `sslmode=require` encrypts traffic but does not provide the stricter hostname verification of `verify-full`. It remains unchanged for deployment compatibility. |
| Least-privilege database access | Runtime repositories only SELECT from DS-managed `citysense` tables. A SELECT-only runtime role is suitable for the current application. | Dedicated Neon runtime role used by Render `DATABASE_URL` | Repository tests confirm read-only access patterns; route generation tests confirm no persistence write. | Role grants must be reviewed and applied manually in Neon. Loading/admin credentials must remain separate. |
| External API key protection | Pelias and ORS calls are made by Flask; the key is read from the backend environment and is never included in frontend responses. | `OPENROUTESERVICE_API_KEY` | Geocoding, routing, and API safety tests use fake clients and fake keys. | Provider-side quotas and key rotation remain operational responsibilities. |
| Automated regression checks | Backend tests cover authentication, cookies, HSTS, CORS, headers, validation, safe failures, and secret-safe responses. | `python -m pytest backend/tests -q` | Run locally and in CI before release. | Automated tests do not replace deployment review, dependency review, or penetration testing. |

## Production checklist

1. Set `ENABLE_DEMO_AUTH=true` in Render.
2. Store a Werkzeug hash—not the plaintext password—as
   `DEMO_ACCESS_PASSWORD_HASH`.
3. Set a separate random `SESSION_SECRET_KEY`.
4. Set `ALLOWED_ORIGINS` to the final Render HTTPS origin.
5. Use the Neon SELECT-only runtime role in `DATABASE_URL` and retain
   `sslmode=require`.
6. Confirm `/api/health` is public, `/` redirects to `/login`, and protected
   APIs return 401 before login.
