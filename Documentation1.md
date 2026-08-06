# CitySense - Iteration 1 Review

Review date: 6 August 2026.
Branch: `liam`.

This document records three things: a check of every user story in *Onboarding requirements.pdf* against its Acceptance Criteria, the frontend copy problems found and fixed, and the data load performed from `data/processed/analysis_hourly.csv`.

Verification was done by running the application end to end - backend on Flask, frontend on Vite, real database, real browser - not by reading code alone.

---

## 1. Summary

| Area | Result |
| --- | --- |
| User stories fully satisfied | 3 of 5 (US 1.1, US 1.3, US 2.2) |
| User stories partly satisfied | 2 of 5 (US 1.2, US 2.1) |
| Epic 1 Definition of Done | 5 of 8 met |
| Epic 2 Definition of Done | 4 of 7 met |
| Frontend copy defects fixed | 9 |
| Accessibility defects fixed | 2 |
| Data pipeline defects fixed | 1 |

The two partly-satisfied stories are not blocked by broken code. Both are blocked by missing inputs: a public transport dataset that was never onboarded, and a refuge register that is a quarter of its planned size.

---

## 2. User stories against Acceptance Criteria

### US 1.1 - Sensory indicator per route

> As a sensory-sensitive commuter, I want to see a sensory indicator (High or Low) for different routes, so that I can choose the path that feels safest and least overwhelming.

**Status: satisfied.**

`POST /api/routes` returns two routes, each carrying `sensory_indicator` of `LOW`, `HIGH`, or `NO_DATA`, plus a `peak_load` band and a plain-language explanation. The indicator is computed in `backend/services/scoring.py:309` from the route's worst segment, not its average - this is the peak-based scoring the pitch is built on, and it is implemented as described.

`NO_DATA` is a genuine third state, not a silent `LOW`. A route with thin sensor coverage, stale counts, or fallback data is labelled as unknown rather than presented as calm. That behaviour is locked by tests at `backend/tests/test_scoring.py`.

### US 1.2 - Avoid congested corridors

> As a sensory-sensitive commuter, I want to avoid highly congested pedestrian corridors, so that I can reduce exposure to crowd-related stress.

**Status: partly satisfied.**

Working: given two candidate routes, the recommendation correctly avoids the congested one. Verified directly - with a busy corridor (900 people) and a calm one (80), at `LOW` tolerance the system recommends the calm route and marks the busy one as above the limit. The crowd tolerance slider genuinely changes the recommendation.

Gap: routes come from OpenRouteService `foot-walking` with the standard alternative-routes option. The system **chooses between** the alternatives it is given by sensory load; it does not **generate** a route that steers around congestion. If the routing service returns two similarly busy alternatives, there is no calmer third option to offer. The story says "avoid congested corridors"; what is delivered is "pick the least congested of the offered corridors".

This is a reasonable Iteration 1 scope, but it should be stated plainly rather than demonstrated as full congestion-aware routing.

### US 1.3 - Alternative route when threshold exceeded

> As a sensory-sensitive commuter during peak hour, I want alternative low-stimulation routes when crowd density exceeds my preferred threshold.

**Status: satisfied.**

`POST /api/routes/monitor` takes the remaining route geometry and the user's tolerance, and reports whether a breach lies ahead, which segment, and the observed peak. Verified: a busy corridor at `LOW` tolerance returns `breached: true` with segment index and the message "It gets high ahead. You can switch to a calmer route." A calm route returns no breach.

The frontend polls this during navigation and offers a reroute. Monitoring refuses to report on stale or fallback data rather than guessing.

### US 2.1 - Identify nearby sensory refuge locations

> As a sensory-sensitive commuter, I want to identify nearby sensory refuge locations such as parks, libraries and quiet public spaces so that I can take breaks when feeling overwhelmed.

**Status: partly satisfied.**

Working: `GET /api/refuges` returns refuges sorted by distance with bearing and direction. Overwhelm Mode collapses to a single arrow, a distance, and one place name, as specified on slide 13. Records are labelled unverified, which is honest.

Two gaps against the plan:

1. **Register size.** Slides 7 and 10 promise a hand-curated register of 12-15 CBD refuges. `backend/data/refuges.py` contains **4**. That is roughly a third of the stated scope.
2. **Register composition.** All 4 are outdoor lawns and forecourts - State Library forecourt, Carlton Gardens south lawn, Treasury Gardens western lawn, Birrarung Marr upper terrace. The story explicitly names "parks, **libraries** and quiet public spaces". No indoor refuge exists, so the feature currently fails anyone needing shelter in rain, heat, or after dark. Opening hours and lighting fields are defined in the schema but unpopulated.

The database refuge table is empty, so the app falls back to these 4 curated records. Expanding the register is data entry against an existing, working schema - no code change is needed.

### US 2.2 - Predictive alerts for the next hour

> As a sensory-sensitive commuter, I want predictive alerts showing which areas are likely to become overwhelming within the next hour, so that I can adjust my travel plans proactively.

**Status: satisfied** (this was previously blocked; the data load in section 4 unblocked it).

Verified against the newly loaded profiles for Tuesday 17:00:

```
predicted_peak: HIGH (2962)   confidence: HIGH
basis: Based on the same weekday and hour in past weeks
alert: "Likely high in about 10 minutes, based on past weeks."
segment samples: 104 and 36 past observations
```

Alerts fire only between 5 and 60 minutes ahead, only above the user's tolerance, and only at MEDIUM confidence or better. Confidence is derived from sample count and coefficient of variation, so a volatile hour is labelled low confidence instead of being asserted - this is the trust mechanism from slide 12, and it works.

Prediction is honest about absence: where no past pattern exists for a sensor at that weekday and hour, the route reports it as unavailable rather than inventing a number.

---

## 3. Definition of Done

### Epic 1

| Criterion | Status |
| --- | --- |
| User can enter a CBD destination | Met - address autocomplete with explicit confirm step |
| At least one sensory-aware route from CoM open data | Met - two routes, scored on real pedestrian counts |
| Routes assigned a sensory indicator | Met |
| Recommendations adjust when crowd levels exceed limits | Met |
| **Walking routes integrate with public transport access points** | **Not met** |
| **Accessibility and usability testing with representative users** | **Not met** |
| Critical and high-priority defects resolved | Met for defects found in this review (section 5) |
| **Acceptance criteria approved by mentors** | **Outstanding** - requires mentor sign-off |

**Public transport integration** is entirely absent. There is no PTV or GTFS dataset, no tram or train stop layer, and no station entry points in routing. Slide 14 onboards four datasets, none of which carry public transport. The epic goal names "train, tram and on foot" travel; only the walking leg exists. This is a scoping gap that predates the code - the dataset was never onboarded.

**Accessibility testing** has one automated keyboard test. Slide 8 allocates D6 to accessibility and usability testing, and slide 21 flags reaching neurodivergent participants as an open risk. No session records exist in the repository. The contrast defects in section 5 - one of which made body text effectively unreadable - would very likely have been caught by the planned testing, which is evidence the gap is material rather than procedural.

### Epic 2

| Criterion | Status |
| --- | --- |
| Real-time alerts for high-density areas | Met - live monitoring endpoint |
| Refuge locations displayed on demand | Partly met - only 4 refuges, all outdoor |
| Predictive alerts from historical trends | Met - see US 2.2 |
| **Alert accuracy validated against city data** | **Not met** |
| Critical and high-priority defects resolved | Met for defects found in this review |
| **Accessibility testing completed and approved** | **Not met** |
| **Acceptance criteria approved by mentors** | **Outstanding** |

**Accuracy validation** is the most substantive remaining gap. Slide 10 commits to validating predictions against held-out weeks, and slide 17 justifies the descriptive-statistics approach on the grounds that it is checkable. The profile table now holds two years of data (2024-04-23 to 2026-04-22), so a held-out validation is straightforward: build profiles on data up to a cut-off, then score predictions against the weeks after it. Nothing in the codebase does this yet, so the confidence labels are calibrated on assumption rather than measurement.

### Other plan claims

Slide 19 states CI runs "ESLint, Prettier, Vitest and the production build". `.github/workflows/ci.yml` runs pytest, Vitest and the build. There is no ESLint or Prettier configuration in the repository. Either wire them up or amend the claim.

---

## 4. Data load

Source: `data/processed/analysis_hourly.csv` - 1,497,403 rows, 100 sensors, 2024-04-23 to 2026-04-22. This is the hourly pedestrian dataset referred to in the request; the file is named `analysis_hourly.csv`, not `pedestrian_hourly.csv`, and is a wide join of pedestrian counts with microclimate and canopy attributes.

The loader expects three normalised files, so a new script derives them:

`scripts/build_processed_datasets.py` projects the wide extract onto the documented contract:

| Output | Rows | Notes |
| --- | --- | --- |
| `sensor_locations.csv` | 100 | coordinates split into latitude/longitude (1NF, per the plan) |
| `pedestrian_readings.csv` | 56,082 | trailing 28 days, hourly, composite natural key |
| `sensor_historical_profiles.csv` | 16,695 | mean, median, 80th percentile, standard deviation per sensor per weekday-hour |

Loaded and verified via `/api/data/status`: 100 sensors, 56,082 readings, 16,695 profiles. Re-running the load produces identical counts, confirming the upserts are idempotent.

Profile quality: all 100 sensors have profiles, several with the full 168 weekday-hour cells, averaging 89.7 observations per cell. Cells with fewer than 4 observations are not published - a median over two Tuesdays is not a baseline, and publishing it would give the confidence labels something unearned to report.

Timestamps are anchored to Melbourne local time before deriving weekday and hour, so predictions align with the city the user is walking in.

Refuges were not loaded: no `data/processed/refuges.csv` exists. The application falls back to the 4 curated records discussed under US 2.1.

### Pipeline defect found and fixed

The first load failed. `scripts/load_data.py` built a single multi-row INSERT for an entire dataset; at 56,082 rows across 8 columns this exceeds SQLite's 32,766 bind-variable limit, and the loader reported only a sanitised "Database load failed". The insert is now chunked per dialect. A regression test (`test_loader_handles_more_rows_than_sqlite_bind_variable_limit`) loads 4,200 rows and fails without the fix.

This would have blocked any real extract, not just this one.

---

## 5. Frontend defects found and fixed

### Tone

The two strings raised in review were symptoms of a consistent pattern, so the whole user-facing surface was reviewed rather than the two lines alone. The product voice - "Choose a route with less guesswork", "Nothing above Moderate" - is plain and calm. Much of the runtime copy was written from the system's point of view.

| Before | After |
| --- | --- |
| Live data from 27 nearby sensors with 100% coverage. | Based on live counts from 27 sensors along this route. |
| Historical profile data has not been loaded. | We have no past pattern for this route at this time of day. |
| Prototype route; confidence is low. | This is an example route, not a live one. |
| Current observed peak / Coverage | Busiest point / Route checked |
| Predicted peak: Moderate - MEDIUM confidence | Likely moderate when you get there - Fairly confident |
| Nearby prototype refuges | Quiet places nearby |
| Historical prediction unavailable. | We cannot say how busy this will be. |

The wording "Historical profile data has not been loaded" was also **factually wrong** in the common case. It was returned whenever a lookup missed, including when the table was fully populated but held no row for that sensor at that weekday and hour. During this review it appeared on screen while 16,695 profiles were loaded. The replacement states what is true from the reader's side.

Care was taken not to soften honest limitations. Unverified refuges are still labelled unverified, example routes are still labelled examples, and missing data is still refused rather than filled in.

### Raw exception text reaching users

`"Failed to fetch"` - the browser's own wording for a network error - was displayed directly in the interface. Four call sites passed `error.message` straight to the screen.

Fixed with `frontend/src/userMessages.js`: only messages explicitly written for a person (`UserFacingError`) are shown; anything else falls back to calm wording. Regression test asserts a raw `TypeError("Failed to fetch")` never reaches the user.

Related: the backend returned "The HeiGIT API key is not configured" and "Live routing authentication failed" to users. Both named internal concerns the reader cannot act on. Failure causes are still logged by category for debugging.

### Accessibility

Two defects, both on the primary decision screen:

1. **Route cards were unreadable.** `levelClass()` was applied to the whole card and to the small level pill. The rule `.level-high { background: var(--color-high) }` was written for the pill but flooded the entire card in solid dark red, leaving body text at **1.21:1** and some values at **1.08:1** (white on near-white). WCAG AA requires 4.5:1. Strong fills are now scoped to pills and segment bars; cards use the existing soft tints.

2. **Muted text failed AA on tinted surfaces.** `--color-muted: #526966` measured 4.39:1 on the tinted cards. Darkened to `#465957`, which clears AA on every surface it is used on (minimum 5.54:1).

After the fixes, an audit of every text node on the results screen - accounting for the large-text exemption - reports **zero contrast failures**.

Slide 13 lists "WCAG AA contrast on all text" as a UX rule, so these were defects against the team's own stated standard.

### Duplicated line

The route card printed the confidence explanation, then listed all confidence reasons - and the explanation is always the first reason. Users saw the same sentence twice in a row. The list now excludes the line already shown, covered by a regression test.

---

## 6. Verification

All checks run on the `liam` branch after the changes above.

```
backend:  79 passed
frontend: 20 passed (node), 10 passed (vitest)
contrast: 0 failures on the route results screen
data:     100 sensors, 56,082 readings, 16,695 profiles; reload is idempotent
```

Six tests asserted on exact old copy. They were updated to assert the intended meaning - that missing data is never presented as calm, that an example route says so, that a failing lookup does not claim a load level - rather than on brittle sentence fragments, so the same protection survives future wording changes.

One pre-existing test failure was also fixed: `test_missing_optional_files_are_reported_and_strict_mode_fails` read the real `data/processed/` directory and passed only while that directory was empty. It now points at an isolated temporary directory.

---

## 7. Recommended next steps

Ordered by how much each affects a real user of the product.

1. **Expand the refuge register to 12-15 places, including indoor ones.** Currently 4, all outdoor. Data entry only - schema, API, and Overwhelm Mode already work. Highest user impact for the least effort, and it closes the largest gap in US 2.1.
2. **Run the accessibility and usability testing already planned for D6.** The contrast defects found here support the case that this step is doing real work.
3. **Validate prediction accuracy against held-out weeks.** Committed to on slide 10 and now practical: two years of profile data are loaded. Without it, confidence labels are uncalibrated.
4. **Decide publicly on public transport.** Either onboard a PTV dataset and integrate stop access points, or restate Epic 1 as walking-only for Iteration 1. The current plan claims an integration that does not exist.
5. **Reconcile the CI claim.** Add ESLint and Prettier, or amend slide 19.

Items 4 and 5 are honesty-of-reporting issues rather than product defects, but both are visible to mentors assessing the Definition of Done.
