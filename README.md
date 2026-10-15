
# Urban Accessability Analysis - Hyderabad



https://github.com/user-attachments/assets/f8270ab3-c7bb-4d49-b6a6-7a7e134d7cb0



An interactive walkability-mapping tool covering all 145 municipal wards of Hyderabad. Rather than a single static "walkability score," it computes real 15-minute pedestrian access to five essential amenity categories using actual street networks, statistically classifies which parts of the city form genuine accessibility clusters versus noise, and lets you simulate the effect of adding a new amenity anywhere on the map.

## What it does

- Rates each of the 145 parts of the city with a score that shows how easy it is to walk to hospitals, pharmacies, schools, parks and grocery stores
- Uses maps from OpenStreetMap to find the shortest walking paths, not just straight lines
- Classifies each ward as a statistically significant accessibility hotspot, coldspot, or outlier via Local Moran's I (LISA) spatial autocorrelation
- Lets you click on any place on the map choose a type of place and see how the walkability would change if that place existed
- Has a way to find a specific part of the city a map that shows access scores and a list that explains each score

## How the Access Index works

| Step | Method |
|---|---|
| Reachability | Dijkstra shortest-path search from each amenity over the real walking network, capped at a 15-minute travel-time cutoff |
| Per-category score | Count of each amenity type reachable per street-network node, min-max normalized against that ward's own historical range (0–100) |
| Composite index | Mean of the five normalized category scores per node, then averaged across all nodes in a ward |
| Hotspot classification | Local Moran's I (via `esda`/`libpysal`) on the composite index, using Queen contiguity between ward neighbors — flags each ward as High-High, Low-Low, High-Low, Low-High, or Not Significant |

The "what-if" simulator reuses the same scoring pipeline against a ward's cached network, so a hypothetical amenity is evaluated exactly the way real amenities were — not a simplified approximation.

## Architecture

```
OpenStreetMap PBF extract + ward boundaries
    -> scripts/build_all_wards.py  (network loading, scoring, LISA — resumable, all 145 wards)
    -> data/ward_scores_final.geojson + data/ward_cache/ (per-ward graphs + amenities)
    -> api/main.py  (FastAPI — serves precomputed scores, runs live /simulate on cached data)
    -> frontend/index.html  (Leaflet + vanilla JS)
```

## Tech stack

- **Geospatial processing:** Python, `pyrosm`, `osmnx`, `networkx`, `geopandas`, `shapely`
- **Spatial statistics:** `esda`, `libpysal`
- **Backend:** FastAPI, `uvicorn`
- **Frontend:** Leaflet.js, vanilla JavaScript
- **Testing:** `pytest`
- **Deployment:** Render (backend), Vercel (frontend)

## Data sources

- Street network & amenities: [OpenStreetMap](https://www.openstreetmap.org/copyright), © OpenStreetMap contributors, licensed under [ODbL](https://opendatacommons.org/licenses/odbl/)
- Ward administrative boundaries: [bharatlas.com](https://bharatlas.com) / OpenCity — note: the source GeoJSON stores coordinates in (lat, lon) order rather than the GeoJSON standard (lon, lat); this repo corrects it in `wards.py`'s `load_wards()`, and any code reading the raw file directly must apply the same fix

## Running locally

**Backend:**
```bash
python -m venv venv && venv\Scripts\activate
pip install -e .
pip install -r requirements.txt
uvicorn api.main:app --reload
```
Runs on `http://127.0.0.1:8000` — visit `/wards` to confirm it's serving data.

**Frontend:**
```bash
cd frontend
python -m http.server 5500
```
Open `http://127.0.0.1:5500`. Update the `API_BASE` constant near the top of `index.html`'s `<script>` block to point at `http://127.0.0.1:8000` for local testing, or leave it on the deployed Render URL to test against production.

**Running tests:**
```bash
pytest tests/
```
No data files or network access required — runs entirely against small synthetic graphs.

**Regenerating the data from scratch** (only needed when changing scoring logic or adding a category; requires the raw `southern-zone.osm.pbf` extract, ~530MB, not included in this repo):
```bash
python scripts/build_all_wards.py     # resumable — safe to re-run if interrupted
python scripts/make_map.py            # optional: static folium map for reporting
```

## Known limitations

- The Access Index is an unweighted average across street-network nodes — it does not account for population density, so a sparsely populated ward and a dense residential one are treated equally.
- The 15-minute cutoff is a fixed assumption, not sensitivity-tested against alternative cutoffs in this version.
