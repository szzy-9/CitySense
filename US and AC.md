# User Story 1.1: Sensory Intensity Route Indiators
User story: As a sensory-sensitive commuter, I want to see a High / Low sensory indicator for each route, so I can choose the path that feels safest.

Data source: Pedestrian Counts per Hour, Sensor Locations.

Benefit: Increased confidence in independent travel.

Definition of Done:
- Every route returns a High/Low band
- Render with text + color
- Code reviewed and merged
 
## AC 1.1a - Indicator shown on every route
Given the user opens the route comparison screen

When a user has entered a destination within the CBD and the system has generated route options

Then the system displays a High or Low sensory indicator on every route shown, calculated from that route's Pedestrian Counts per Hour and Sensor Locations data.

## AC 1.1b - Indicator visible before selection
Given the user looks at a specific route without tapping into it

When a user is comparing two or more routes on screen

Then the system already shows that route's sensory indicator alongside it, so no extra action is needed to see the rating.

# User Story 1.2: Default away from congestion
User story: As a sensory-sensitive commuter, I want to be routed away from congested corridors by default, so my trip avoids crowd stress from the start rather than reacting to it.

Data source: Real-time Pedestrian Counting System.

Benefit: Reduced exposure to high-density areas.

Definition of Done:
- Congestion threshold excluded by default
- Unit test: exclude when alternative exists
- Code reviewed and merged

## AC 1.2a - Congestion avoidance is the default
Given the system generates the route

When a user requests a route to a destination and a lower-congestion path exists

Then it automatically excludes segments above the congestion threshold without the user having to enable any setting first.

## AC 1.2b - Reason shown when congestion is unavoidable
Given the user enters the origin and destination

When a user requests a route where every available path crosses a congested segment

Then map view display the user a short explanation of why the congested segment could not be avoided, instead of presenting it silently.

# User Story 1.3: Reroute on live threshold breach
User story: As a sensory-sensitive commuter, I want an alternative route the moment live crowding crosses my threshold, so the plan adapts in real time instead of only at the start of the trip.

Data source: Pedestrian Counts per Hour (historical).

Benefit: Higher route completion without distress.

Definition of Done:
- Route adjust mid-trip, form current position
- Reroute time budget tested on device
- Code reviewed and merged

## AC 1.3a - Live threshold breach is detected mid-trip
Given the user is on the map page

When the user is actively walking around and set threshold is reached

Then the system detects the breach in real time without the user needing to check manually.

## AC 1.3b - Alternative route offered without restarting
Given a user on an active route suddenly encountered a condition that breach their sensory threshold

When the user reports a sensory issue on the route

Then interface presents an alternative route calculated from the user's current position, so the user can keep moving without re-entering their destination or restarting the trip.

# User Story 2.1: Find nearby refuge
User story: As a sensory-sensitive commuter, I want to find nearby refuge locations such as parks, libraries and quiet public spaces, so I can take a break when overwhelmed.

Data source: Landmarks & Places of Interest, plus curated refuge register.

Benefit: Improved perception of safety and comfort.

Definition of Done:
- Query test against sample CBD locations, returns type and distance
- Code reviewed and merged

## AC 2.1a - Refuges shown from current location
Given the user opens the refuge finder without having planned any route

When a user is standing somewhere in the CBD and feels overwhelmed

Then the system shows nearby parks, libraries, and quiet public spaces based on the user's current location.

## AC 2.1b - Refuge listing shows type and distance
Given a user is viewing the list of nearby refuges

When the user looks at any individual result

Then the system shows that refuge's type and its distance or walking time from where the user currently is, so the user can judge which one they can actually reach.
