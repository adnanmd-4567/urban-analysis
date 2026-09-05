# API serving precomputed ward scores, plus a live what-if simulation.

import pickle
from pathlib import Path
import geopandas as gpd
import networkx as nx
import osmnx as ox
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from shapely.geometry import Point
from shapely.geometry import Point as ShapelyPoint
from urban_analysis.config import TIME_CUTOFF_SECONDS
from urban_analysis.network import add_hypothetical_amenity
from urban_analysis.scoring import score_all_points, normalize_and_combine, normalize_with_fixed_bounds
from urban_analysis.wards import load_wards

CATEGORIES = ["grocery", "hospital", "pharmacy", "park", "school"]

from api.schemas import SimulationRequest, SimulationResult

app = FastAPI(title="Urban Access Atlas API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CACHE_DIR = Path("data/ward_cache")

_wards_scored = None
_wards_raw = None

@app.on_event("startup")
def load_data():
    global _wards_scored, _wards_raw

    # _wards_scored (ward_scores_final.geojson) only contains wards that finished processing successfully — 
    # currently all 145, but if you regenerate ward_results.csv with new logic, some wards may temporarily 
    # be absent here. /simulate on an unscored ward will 404.

    _wards_scored = gpd.read_file("data/ward_scores_final.geojson")
    _wards_raw = load_wards("data/wards_hyderabad.geojson")

@app.get("/wards")
def get_wards():
    return _wards_scored.__geo_interface__

# Uses cached per-ward graphs/amenities from data/ward_cache/ (built by build_all_wards.py) rather than 
# re-parsing the PBF live — this is what makes simulation requests fast enough for interactive use. 
# If a ward's cache is missing, this endpoint has no fallback and will error; see scripts/rebuild_cache.py 
# to regenerate it if ward_cache/ is ever lost.

@app.post("/simulate", response_model=SimulationResult)
def simulate(req: SimulationRequest):
    if req.category not in CATEGORIES:
        raise HTTPException(400, f"category must be one of {CATEGORIES}")

    pin = Point(req.lon, req.lat)
    containing = _wards_raw[_wards_raw.geometry.contains(pin)]
    if containing.empty:
        raise HTTPException(404, "That point doesn't fall inside any known ward")

    ward_name = containing.iloc[0]["Name"]
    safe_name = ward_name.replace(" ", "_")

    matching_scored = _wards_scored[_wards_scored["Name"] == ward_name]
    if matching_scored.empty:
        raise HTTPException(
            404,
            f"{ward_name} hasn't been processed yet — click inside one of the "
            f"completed wards: {_wards_scored['Name'].tolist()}"
        )
    scored_row = matching_scored.iloc[0]
    bounds = {cat: (scored_row[f"{cat}_bound_lo"], scored_row[f"{cat}_bound_hi"]) for cat in CATEGORIES}

    cache_graph_path = CACHE_DIR / f"{safe_name}.pkl"
    cache_amenities_path = CACHE_DIR / f"{safe_name}_amenities.geojson"
    if not cache_graph_path.exists():
        raise HTTPException(500, f"No cached data for {ward_name} — run build_all_wards.py first")

    with open(cache_graph_path, "rb") as f:
        G = pickle.load(f)
    amenities = gpd.read_file(cache_amenities_path)

    same_category = amenities[amenities["category"] == req.category]
    distances = same_category.geometry.distance(pin)  # degrees, since CRS is EPSG:4326
    already_exists_nearby = bool((distances < 0.001).any())  # ~100m at this latitude

    new_node = ox.distance.nearest_nodes(G, X=req.lon, Y=req.lat)
    affected_nodes = list(nx.single_source_dijkstra_path_length(
        G, new_node, cutoff=TIME_CUTOFF_SECONDS, weight="travel_time"
    ).keys())

    scores_before = score_all_points(affected_nodes, G, amenities, categories=CATEGORIES)
    scores_before = normalize_with_fixed_bounds(scores_before, CATEGORIES, bounds)
    amenities_after = add_hypothetical_amenity(amenities, req.lon, req.lat, req.category, G)
    scores_after = score_all_points(affected_nodes, G, amenities_after, categories=CATEGORIES)
    scores_after = normalize_with_fixed_bounds(scores_after, CATEGORIES, bounds)

    return SimulationResult(
        ward=ward_name,
        category=req.category,
        access_index_before=scores_before["access_index"].mean(),
        access_index_after=scores_after["access_index"].mean(),
        delta=scores_after["access_index"].mean() - scores_before["access_index"].mean(),
        category_count_before=scores_before[req.category].mean(),
        category_count_after=scores_after[req.category].mean(),
        already_exists_nearby=already_exists_nearby,
    )