PLACES = [
    {
        "id": "federation-square",
        "name": "Federation Square",
        "lat": -37.81798,
        "lon": 144.96913,
    },
    {
        "id": "queen-victoria-market",
        "name": "Queen Victoria Market",
        "lat": -37.80758,
        "lon": 144.95678,
    },
    {
        "id": "flinders-street-station",
        "name": "Flinders Street Station",
        "lat": -37.81827,
        "lon": 144.96706,
    },
    {
        "id": "state-library-victoria",
        "name": "State Library Victoria",
        "lat": -37.80981,
        "lon": 144.96519,
    },
    {
        "id": "southern-cross-station",
        "name": "Southern Cross Station",
        "lat": -37.81833,
        "lon": 144.95274,
    },
    {
        "id": "carlton-gardens",
        "name": "Carlton Gardens",
        "lat": -37.80500,
        "lon": 144.97120,
    },
]


def find_place(place_id):
    for place in PLACES:
        if place["id"] == place_id:
            return place
    return None

