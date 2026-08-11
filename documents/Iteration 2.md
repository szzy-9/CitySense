# Missing AC
## AC 2.2a - Alert triggers from historical trend data
- Given system generates the prediction: the area user walking toward will become overwhelming within the next hour
- When a user is walking toward an area that historical pedestrian trends predict 
- Then it sends the user an alert before they reach the area.

## AC 2.2b - Alert arrives with enough lead time to act
- Given the system has generated an overwhelm alert for an area the user is approaching
- When user receives it with enough lead time before entering the zone
- Then the user can change direction or delay their trip, rather than receiving it after they have already arrived.