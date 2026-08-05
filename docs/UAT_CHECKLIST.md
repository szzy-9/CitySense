# User Acceptance Test Checklist

Automated results must come from the test commands. Manual evidence remains required where indicated.

| Test ID | Given / precondition | When / action | Expected result | Type | Evidence still required |
| --- | --- | --- | --- | --- | --- |
| ROUTE-01 | Two real ORS alternatives are returned | The backend normalizes them | GeoJSON, distance, duration, and steps are preserved | Automated fake client + manual live smoke | Deployed live screenshot/network record |
| ROUTE-02 | HeiGIT is unavailable | A route is requested | Two `PROTOTYPE` routes contain LOW confidence and a safe fallback reason | Automated | None beyond CI result |
| IND-01 | A route has reliable data within tolerance | The route card renders | LOW text, icon, and visual style are visible without a click | Automated component | Manual keyboard/visual check |
| IND-02 | A route has reliable data above tolerance | The route card renders | HIGH text and non-colour cue are visible | Automated logic/component coverage | Manual visual check |
| IND-03 | Reliable coverage is insufficient | The route card renders | NO DATA is shown and never formatted as Low | Automated | Manual visual check |
| REC-01 | Fastest is HIGH and another route is LOW | Routes are scored with LOW tolerance | The LOW route is recommended by default | Automated backend | Live-data scenario if available |
| REC-02 | Every observed route exceeds tolerance | Routes are scored | Lowest observed peak is recommended and congestion avoidable is false | Automated backend | Manual copy review |
| REC-03 | Every candidate is NO_DATA | Routes are scored | No congestion-avoidance claim is made | Automated backend/frontend | Manual visual check |
| NAV-01 | Active Navigate has current position | Position updates | Current marker and accuracy update; route state remains unchanged | Manual + helper tests | Real-device recording |
| NAV-02 | Follow Mode is active | User drags/zooms then presses Re-centre | Follow pauses and resumes | Automated helper | Real browser/map evidence |
| NAV-03 | ORS steps exist | User advances along route | Current instruction, next-step distance, remaining distance/time update | Automated helper | Real-device walkthrough |
| NAV-04 | User is within arrival radius | Position updates | Arrival state appears | Automated helper | Real-device timing/evidence |
| REROUTE-01 | Current position and destination exist | User selects either reroute action | Current position becomes origin; destination and tolerance remain | Automated helper/backend | Browser network evidence |
| REROUTE-02 | A reroute request is active | User presses reroute again | Duplicate request is blocked/disabled | Automated helper/component attribute coverage | Browser rapid-click check |
| REROUTE-03 | Reroute fails | Error is returned | Existing route remains visible with a safe message | Code-path review | Manual network-failure evidence |
| MON-01 | Remaining route contains a live threshold breach | 60-second monitor runs | One alert appears and no ORS call is made by monitor endpoint | Automated backend | Timed browser evidence |
| MON-02 | The same breach repeats | The next monitor response matches | Duplicate alert/reroute preparation is suppressed | Code-path review | Timed browser evidence |
| MON-03 | Alternative is prepared | User has not accepted it | Current route remains active | Code-path review | Browser evidence |
| REF-01 | No route is planned | User chooses Find a Quiet Place and permits location | Several distance-sorted prototype refuges can be shown | Automated backend/component | Real browser evidence |
| REF-02 | Location permission is denied | Finder handles the error | Application remains usable and confirmed-origin fallback is offered | Automated component | Browser permission evidence |
| REF-03 | Refuge results render | User reads a card | Type, straight-line distance, attributes, and unverified disclaimer appear | Automated component | Manual content check |
| DB-01 | `DATABASE_URL` is absent | App starts locally | SQLite is used | Automated configuration/local smoke | None beyond test log |
| DB-02 | Neon URL is present | SQLAlchemy parses it | psycopg 3, SSL requirement, pre-ping, and small pool are configured | Automated | Real Neon connection evidence |
| HEALTH-01 | Database is connected/degraded | `/api/health` is requested | Safe database status appears with no connection details | Automated connected path | Degraded deployment test |
| SEC-01 | Malicious/invalid input is submitted | Backend validation runs | Safe 4xx response; no SQL/stack/key/body is exposed | Automated focused cases | Release secret scan |
| PRIV-01 | Browser location updates | Navigation runs | Precise position remains memory-only and is not logged/stored | Automated storage model check + code review | Runtime log/database inspection |
| DEPLOY-01 | Render/Neon variables are configured | Docker service deploys | One service serves Vue, assets, API, SPA fallback, and health | Manual | Actual URL and deploy logs |
| PERF-01 | Manual reroute is used on a real device | Request and render complete | Development timing is recorded locally without analytics/coordinates | Manual | Real-device timing |
| PRED-01 | No verified historical baseline exists | Prediction is requested/considered | Prediction remains unavailable and no records are fabricated | Documentation/code review | Historical dataset decision |

