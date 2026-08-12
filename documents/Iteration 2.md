# Missing AC
## AC 2.2a - Alert triggers from historical trend data
- Given system generates the prediction: the area user walking toward will become overwhelming within the next hour
- When a user is walking toward an area that historical pedestrian trends predict 
- Then it sends the user an alert before they reach the area.

## AC 2.2b - Alert arrives with enough lead time to act
- Given the system has generated an overwhelm alert for an area the user is approaching
- When user receives it with enough lead time before entering the zone
- Then the user can change direction or delay their trip, rather than receiving it after they have already arrived.

---

What was actually missing

AC 2.2a/2.2b were half met. A stretch above your limit did warn - but the only button was "Check another route", which is right when the crowd is on the way and useless when the crowd is where you are going. Every route ends there. A destination under 5 minutes away raised nothing, and nothing was said at planning, when delaying is still free.

What was built

Alert type: in-app banner, at planning and on approach - your call, and the right one. navigator.vibrate() does not exist in any iOS browser and is ignored in a hidden tab, and this app has no service worker or web manifest, so a browser tab cannot reach a locked phone. A notification path that silently fails on half the devices is worse than a banner that is honest about its reach.

Planning banner (before you commit): names the destination band and the hour you actually get there, plus "No route avoids it" when congestion_avoidable is false. Offers the departure_suggestion that clears the peak, absorbed into the same panel rather than stacked as a second notice. No reroute button.

Approach banner (within 15 minutes of arrival): counts down, offers quiet places near the destination, and "Keep going". No delay button - someone already walking no longer has that choice. 15 minutes rather than the stretch warning's 5, because deciding to be somewhere else takes longer than stepping onto a different street. Clears on arrival.

The stretch warning now skips the final segment, so one place never gets two banners. Refuge list opens seeded with the destination, not the start. No backend change - every field was already in the response.

Two bugs the walkthrough found

- A trip planned at 2am for a Friday 5pm departure said it would arrive "around 2am", then flagged the 5pm pattern it had just read correctly as the wrong one. Arrival is now counted from the chosen departure. Live proof: banner read (2am) before, (5pm) after.
- An animated scroll never runs in a tab nobody is looking at, so pressing Find Routes and switching away left the routes off screen on return. Now verified and re-done without animation if it did not happen - confirmed working in a hidden: true tab.