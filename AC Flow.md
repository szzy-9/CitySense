# AC Flow

How a user reaches each acceptance criterion in the app, and what was seen when it was walked through.

Tested 10 August 2026, roughly 18:00 Melbourne time, against the live stack: OpenRouteService walking routes, the live City of Melbourne pedestrian feed, and the imported historical profiles in `citysense.db`.
Trip used throughout: Current Location (Demo Mode, Flinders Street Station, -37.8183 144.9671) to Melbourne Museum, Carlton.
Crowd tolerance Low unless a step says otherwise.

Two ACs depend on the hour being busy in the historical record.
Where the 18:00 profile is quiet, the flow is recorded against a 13:00 departure, which is a normal use of the Leaving field, and the quiet-hour result is reported too because a warning that stays silent when nothing is coming is the correct behaviour, not a gap.

---

## US 1.1 - Sensory intensity route indicators

### AC 1.1a - Indicator shown on every route

**Flow**

1. Open the app. Tap **Use Current Location** for FROM.
2. Type a destination in TO, pick a suggestion from the list. The label under the field reads "Confirmed:".
3. Leave the crowd tolerance where it is and tap **Find Routes**.
4. Read the ROUTE COMPARISON list.

**Seen:** all three returned routes carry a banded indicator, none blank.

| Route | Role | Indicator | Busiest point | Coverage |
|---|---|---|---|---|
| route-1 | Fastest | High, "Above your crowd limit" | High | 75% |
| route-2 | Alternative | High, "Above your crowd limit" | High | - |
| route-3 | Calmest, Recommended | High, "Above your crowd limit" | High | - |

Each card also shows the step-by-step band strip, the confidence, the share of the route that has sensors nearby, and the street chain the route follows.
Where a stretch has no sensor near it, the strip renders it hatched as No Data rather than colouring it Low.

### AC 1.1b - Indicator visible before selection

**Flow**

1. From the ROUTE COMPARISON list produced above, do not tap into any route.
2. Scroll the list.

**Seen:** the indicator, minutes, distance, band strip and busiest-point label are all on the card itself.
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
At its default of Medium the same selection runs; no first-time setup step exists.

### AC 1.2b - Reason shown when congestion is unavoidable

**Flow**

1. Plan the same trip at tolerance Low, an hour when the CBD is busy.
2. Read the recommended card.

**Seen:** every route crossed a High stretch, so the recommendation named it instead of quietly serving the least bad option:

> Every route today goes above your crowd limit somewhere. This one stays the calmest at its busiest point.

`congestion_avoidable` was false for that request, and each non-recommended card said "This route goes above your crowd limit."
Where the High stretch is the doorstep rather than a choice, the card separates the two: "High near the start and end, which no route avoids. Nothing above moderate in between."
Where waiting would clear the peak, a departure suggestion is offered instead; none was available for this trip, so nothing was invented.

---

## US 1.3 - Reroute on live threshold breach

### AC 1.3a - Live threshold breach is detected mid-trip

**Flow**

1. From the comparison list, tap **Navigate using the calmest route**.
2. Stay on the navigate screen. Do not press anything.

**Seen:** within one monitoring cycle the CROWD CHANGE AHEAD banner appeared by itself:

> It gets high ahead. You can switch to a calmer route.
> The current route remains active until you choose an alternative.

The check runs every 60 seconds against the geometry still ahead of the tracked position, so it re-asks as the walker moves, and it is silent when live counts are missing rather than guessing.
The route is never switched without the walker choosing it.

### AC 1.3b - Alternative route offered without restarting

**Flow**

1. With the trip underway, tap **This route feels overwhelming** under CURRENT POSITION. (The prepared alternative on the crowd banner does the same thing in one tap.)
2. Read the result.

**Seen:** the trip continued on the navigate screen, the destination was never re-entered, and the position line changed to "Route updated from your current location." followed by:

> Route checked for a lower-load option. Nothing calmer nearby. This is the calmest option we found.

Recalculated from the current position in 1561 ms end to end (request 1540 ms, render 22 ms).
When a genuinely calmer path exists the same flow reports "There is a calmer way to go." and swaps to it on confirmation.

---

## US 2.1 - Find nearby refuge

### AC 2.1a - Refuges shown from current location

**Flow**

1. From the plan screen, without planning any route, open QUIET PLACES and tap **Find a Quiet Place**.
2. Or, at any point including mid-trip, tap the standing **I'm overwhelmed** button at the bottom of the screen.

**Seen:** 12 curated places ordered by distance from the current position, covering all three kinds the story names - parks (Birrarung Marr, Queen Victoria Gardens, Treasury Gardens, Carlton Gardens, Flagstaff Gardens, Argyle Square), libraries (City Library Flinders Lane, State Library La Trobe Reading Room, Library at the Dock) and quiet public spaces (St Paul's side garden, State Library forecourt, Athenaeum steps).

**I'm overwhelmed** strips the screen back to one instruction - a large arrow, "160 m", the place name, and the direction to walk - because it is meant to be read by someone who is already overloaded.

### AC 2.1b - Refuge listing shows type and distance

**Flow**

1. In the QUIET PLACES list, look at any single result.

**Seen:** each entry leads with its type as a label, then the name, then the distance:

> QUIET PUBLIC SPACE
> St Paul's Cathedral, side garden
> 160 m straight-line distance
> Sheltered garden on the Flinders Lane side, screened from the corner.
> Open to all; services and events may affect access.
> Chosen by us · Not officially verified

Distance is stated as straight-line rather than dressed up as a walking time the app has not calculated, and the provenance line makes clear these are a hand-picked shortlist, not an official register.

---

## US 2.2 - Predictive overwhelm alerts

### AC 2.2a - Alert triggers from historical trend data

**Flow**

1. Plan a trip whose path crosses a stretch that past weeks show busy in the hour ahead. Set Leaving if you want a specific hour.
2. Tap **Navigate using the fastest route**.
3. Read the HISTORICAL OUTLOOK banner without pressing anything.

**Seen:** the banner appeared while the busy stretch was still ahead of the walker:

> Likely moderate in about 6 minutes, based on past weeks.
> We are confident · based on an imported historical baseline, not a live forecast.
> [Check another route] [Keep current route]

The prediction is read per stretch, from the median count for the same weekday and hour in the imported profiles, and only stretches above the walker's own tolerance with MEDIUM confidence or better raise anything.
Example routes never produce a forecast.

At 18:00 on the day of testing every stretch of this corridor was Low in the historical record, and no banner appeared.
That silence is the criterion working: nothing was coming, so nothing was claimed.

### AC 2.2b - Alert arrives with enough lead time to act

**Flow**

1. With the banner showing, keep walking. The stated lead time is recomputed from the tracked position and a clock tick, every position update and at least once a minute.
2. Walk past the stretch.

**Seen**, replaying a live route payload against real geometry, position stepped along the route:

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

---

## Notes

- Both US 2.2 rows are also covered by automated tests in `frontend/tests/routeDisplay.test.js`: alert before the stretch, gone after it, the five-minute floor and its countdown exemption, the one-hour ceiling, tolerance and confidence gating, example routes, and the hour-drift wording.
- OpenRouteService occasionally times out at the six-second budget and the app falls back to example routes, which are labelled "Example route" and are excluded from forecasting on purpose. Retrying Find Routes restores live routing.
- The Definition-of-Done line under US 2.2 about testing prediction accuracy against held-out data is not covered here. It is a data exercise against the imported profiles, separate from the alerting behaviour above.
