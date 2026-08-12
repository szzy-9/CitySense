# AC Flow

How a user reaches each acceptance criterion in the app, and what was seen when it was walked through.

Tested 10 August 2026, roughly 19:30 Melbourne time, against the live stack: OpenRouteService walking routes, the live City of Melbourne pedestrian feed, and the DS-managed `citysense` schema on Neon (`ap-southeast-2`).
Trip used throughout: Current Location (Demo Mode, Flinders Street Station, -37.8183 144.9671) to Melbourne Museum, Carlton.
Crowd tolerance Low unless a step says otherwise.

What the app was reading:

| Table | Rows |
|---|---|
| `citysense.sensor_load_profile` | 12,667 |
| `citysense.sensor_location` | 134 |
| `citysense.sensor_threshold` | 76 |
| `citysense.refuge` | 0 |
| `citysense.refuge_opening_hours` | 0 |

Live pedestrian counts come from the City of Melbourne API, not a table, so they have no row count.
69 sensors matched this corridor, 21 of them along the fastest route.

Because the refuge tables are empty, US 2.1 runs on the curated shortlist built into the app.
That is the app's documented fallback and it is labelled as such on screen, but it is not Neon data.

---

## US 1.1 - Sensory intensity route indicators

### AC 1.1a - Indicator shown on every route

**Flow**

1. Open the app. Tap **Use Current Location** for FROM.
2. Type a destination in TO, pick a suggestion from the list. The label under the field reads "Confirmed:".
3. Leave the crowd tolerance where it is and tap **Find Routes**.
4. Read the ROUTE COMPARISON list.

**Seen:** all three returned routes carry a banded indicator, none blank.

| Route | Role | Minutes | Indicator | Busiest point | Coverage | Confidence |
|---|---|---|---|---|---|---|
| route-1 | Fastest | 25.8 | High, "Above your crowd limit" | High | 75% | High |
| route-2 | Alternative | 25.9 | High, "Above your crowd limit" | High | 75% | High |
| route-3 | Calmest, Recommended | 27.1 | High, "Above your crowd limit" | High | 88% | High |

Each card also shows the step-by-step band strip, the street chain the route follows ("Swanston St → Little Bourke St → Hayward Ln → Exhibition St → Rathdowne St"), where the peak sits ("Busiest near Elizabeth St - Flinders St (East) - New footpath, where it reaches High"), and what the reading rests on ("Based on live counts from 21 sensors along this route").
Stretches with no sensor nearby render hatched as No Data rather than coloured Low.

### AC 1.1b - Indicator visible before selection

**Flow**

1. From the ROUTE COMPARISON list produced above, do not tap into any route.
2. Scroll the list.

**Seen:** the indicator, minutes, distance, band strip, busiest-point label and historical outlook are all on the card itself.
Nothing is behind a tap. Tapping a card only chooses which route the map draws as selected.

---

## US 1.2 - Default away from congestion

### AC 1.2a - Congestion avoidance is the default

**Flow**

1. Plan the trip as above. Do not open any settings, do not enable anything.
2. Read which route carries the RECOMMENDED badge and the sentence under it.

**Seen (tolerance High, where a within-limit path exists):** route-3 was recommended automatically, with the reason "Its busiest point still sits within your crowd limit."
The other two were labelled "Another route stays calmer at its busiest point."
`congestion_avoidable` was true for that request.

The crowd tolerance slider is a limit the recommendation is measured against, not a switch that turns avoidance on.
At its default of Moderate the same selection runs; no first-time setup step exists.

### AC 1.2b - Reason shown when congestion is unavoidable

**Flow**

1. Plan the same trip at tolerance Low or Moderate, an hour when the CBD is busy.
2. Read the recommended card.

**Seen:** at both Low and Moderate every route crossed a High stretch, so the recommendation named it instead of quietly serving the least bad option:

> Every route today goes above your crowd limit somewhere. This one stays the calmest at its busiest point.

`congestion_avoidable` was false, and each non-recommended card said "This route goes above your crowd limit."
The peak here is the doorstep at Flinders Street, which no route can avoid: `unavoidable_level` is High on all three while `avoidable_level` is Moderate on the two calmer ones, and the card separates the two rather than writing off the whole trip.
Where waiting would clear the peak a departure suggestion is offered instead; none was available for this trip, so nothing was invented.

---

## US 1.3 - Reroute on live threshold breach

### AC 1.3a - Live threshold breach is detected mid-trip

**Flow**

1. From the comparison list, tap **Navigate using the fastest route**.
2. Stay on the navigate screen. Do not press anything.

**Seen:** within one monitoring cycle the CROWD CHANGE AHEAD banner appeared by itself:

> It gets high ahead. You can switch to a calmer route.
> The current route remains active until you choose an alternative.

The endpoint reports `breached: true`, `upcoming_peak: HIGH`, `affected_segment_index: 0`, `data_source: LIVE`.
The check runs every 60 seconds against the geometry still ahead of the tracked position, so it re-asks as the walker moves, and it is silent when live counts are missing rather than guessing.
The route is never switched without the walker choosing it.

### AC 1.3b - Alternative route offered without restarting

**Flow**

1. With the trip underway, tap **This route feels overwhelming** under CURRENT POSITION. (The prepared alternative on the crowd banner does the same thing in one tap.)
2. Read the result.

**Seen:** the trip continued on the navigate screen, the destination was never re-entered, and the position line changed to "Route updated from your current location." followed by:

> Route checked for a lower-load option. Nothing calmer nearby. This is the calmest option we found.

Recalculated from the current position in **5492 ms** end to end (request 5463 ms, render 29 ms).
That is a real slowdown: the same reroute measured 1561 ms against the previous local database.
The extra time is the round trip to Neon in `ap-southeast-2` on top of the OpenRouteService call, and it is worth a look before anyone claims a reroute budget on device.
When a genuinely calmer path exists the same flow reports "There is a calmer way to go." and swaps to it on confirmation.

---

## US 2.1 - Find nearby refuge

### AC 2.1a - Refuges shown from current location

**Flow**

1. From the plan screen, without planning any route, open QUIET PLACES and tap **Find a Quiet Place**.
2. Or, at any point including mid-trip, tap the standing **I'm overwhelmed** button at the bottom of the screen.

**Seen:** 12 places ordered by distance from the current position, covering all three kinds the story names - parks (Birrarung Marr, Queen Victoria Gardens, Treasury Gardens, Carlton Gardens, Flagstaff Gardens, Argyle Square), libraries (City Library Flinders Lane, State Library La Trobe Reading Room, Library at the Dock) and quiet public spaces (St Paul's side garden, State Library forecourt, Athenaeum steps).

`refuge_source` reads `CURATED_PROTOTYPE`, because `citysense.refuge` is empty on Neon.
The criterion passes, but on the app's own shortlist rather than DS data, and the screen says so.

**I'm overwhelmed** strips the screen back to one instruction - a large arrow, "160 m", the place name, and the direction to walk - because it is meant to be read by someone who is already overloaded.

### AC 2.1b - Refuge listing shows type and distance

**Flow**

1. In the QUIET PLACES list, look at any single result.

**Seen:** each entry leads with its type as a label, then the name, then the distance:

> QUIET PUBLIC SPACE
> St Paul's Cathedral, side garden
> 160m
> Sheltered garden on the Flinders Lane side, screened from the corner.
> Open to all; services and events may affect access.

Distance is the straight-line metre count, not a walking time the app has not calculated.
The availability line carries whatever caveat the entry itself needs, so a hand-picked shortlist is not read as a guarantee.

---

## US 2.2 - Predictive overwhelm alerts

### AC 2.2a - Alert triggers from historical trend data

**Flow**

1. Plan a trip whose path crosses a stretch that past weeks show busy in the hour ahead.
2. Tap **Navigate using the fastest route**.
3. Read the HISTORICAL OUTLOOK banner without pressing anything.

**Seen:** the banner appeared while the busy stretch was still ahead of the walker:

> Likely moderate in about 6 minutes, based on past weeks.
> Fairly confident · based on an imported historical baseline, not a live forecast.
> [Check another route] [Keep current route]

The Neon profile for this weekday and hour puts the first five stretches of the fastest route at Moderate.
The warning names the fourth of them, because the first three are under five minutes away and too close to act on - the live crowd banner covers those.

Worth recording: the backend's own route-level `prediction_alert` was `null` on all three routes, because its rule suppresses any route with a No Data stretch and every route here loses sensor coverage near Carlton.
The alert on screen comes from the per-stretch selection in the frontend, which warns about the stretch it does have a pattern for.
Without it US 2.2 would show nothing at all on this corridor.

Where the historical record is quiet, no banner appears.
That silence is the criterion working: nothing was coming, so nothing was claimed.

### AC 2.2b - Alert arrives with enough lead time to act

**Flow**

1. With the banner showing, keep walking. The stated lead time is recomputed from the tracked position and a clock tick, on every position update and at least once a minute.
2. Walk past the stretch.

**Seen**, replaying the live Neon route payload against real geometry, position stepped along the route:

| Position along route | Banner |
|---|---|
| 0% | Moderate ahead, 6 minutes |
| 7% | Moderate ahead, 5 minutes |
| 15% | Moderate ahead, 4 minutes |
| 22% | Moderate ahead, 3 minutes |
| 29% | Moderate ahead, 2 minutes |
| 36% onward | nothing |

A new warning is only raised at least five minutes ahead of a stretch, which is the lead time the criterion asks for.
Once raised it keeps counting down rather than disappearing at four minutes, and it stops the moment the walker enters the stretch, where live counts describe the street better than a past pattern can.
It is never shown after the stretch has been passed.

If the trip slips into a later clock hour than the one the outlook was calculated for, the banner says so rather than asserting a stale band: "This reads the 1pm pattern, but you are now due there around 2pm, so check another route for a fresh outlook."

### AC 2.2a and AC 2.2b - where the crowd is the destination itself

The two rows above are answered by rerouting: the busy stretch is on the way, so another street avoids it.
That answer is worthless when the busy place is where the walker is going, and until now it was the only answer offered.
This is the same two criteria, walked against a destination no route avoids.

**Flow**

1. Set Crowd tolerance to Low, and Leaving to Friday 5pm.
2. Plan Spring Street to Bourke Street Mall.
3. Read the banner under the route comparison, before pressing Navigate.
4. Press Navigate and walk the route in.

**Seen** at planning, with the trip still uncommitted:

> WHERE YOU ARE HEADING
> Near your destination is likely high around the time you get there (5pm), based on the same weekday and hour in past weeks. No route avoids it.
> We are confident · based on an imported historical baseline, not a live forecast.
> [Quiet places near there]

The Neon profile puts the final stretch at High with High confidence for Friday 5pm, and `congestion_avoidable` is false on every route, which is what the second sentence reports.
The arrival hour is read off the planned departure rather than the clock, so a trip planned at 2am for a 5pm walk says 5pm.

Where a later departure would clear the peak, `departure_suggestion` is offered inside this panel as "Leave at 5:45 pm instead", rather than as a separate notice about the same trip.
Rerouting is not offered, because no other route ends anywhere else.

**Seen** on approach, position stepped along the route:

| Minutes to arrival | Banner |
|---|---|
| 26 | nothing |
| 16 | nothing |
| 12 | High at the destination, "in about 12 minutes" |
| 10 | High at the destination, "in about 10 minutes" |
| arrived | nothing |

The window is fifteen minutes rather than the five the stretch warning uses.
Choosing somewhere else to be, or turning back, takes longer than stepping onto a different street, and the decision has to be made before the walker is standing in the crowd.
The only actions are "Quiet places near there", which opens the refuge list against the destination rather than the start, and "Keep going".
Leaving later is not offered here, because someone already walking no longer has that choice.

Waving the warning away while planning settles that trip; it does not waive the approach warning, which is the walker's last chance to act.

---

## Notes

- Both US 2.2 rows are also covered by automated tests in `frontend/tests/routeDisplay.test.js`: alert before the stretch, gone after it, the five-minute floor and its countdown exemption, the one-hour ceiling, tolerance and confidence gating, example routes, and the hour-drift wording.
- The destination case adds `frontend/tests/destinationAlert.spec.js`, which plans the trip and walks it in through the screens, and further cases in `routeDisplay.test.js` covering the fifteen-minute window, arrival, the planned-departure arrival hour, and the rule that only one of the two banners speaks for the last stretch.
- Two defects were found during this walkthrough and fixed. The Neon `sensor_location` table keeps the machine code in `sensor_name` and the street in `sensor_description`, and the repository was reading the code, so cards said "Busiest near ElFi_T". And engine pool options were computed once from the environment's database, so with Neon configured the whole backend suite failed at fixture setup before a single test ran.
- The load bands changed with the Neon migration, from 50 and 150 people per minute to 15 and 40. The same corridor that read Low under the old boundaries now reads Moderate to High, which is worth confirming with whoever set them.
- OpenRouteService occasionally times out at the six-second budget and the app falls back to example routes, which are labelled "Example route" and are excluded from forecasting on purpose. Retrying Find Routes restores live routing.
- The Definition-of-Done line under US 2.2 about testing prediction accuracy against held-out data is not covered here. It is a data exercise against the Neon profiles, separate from the alerting behaviour above.
