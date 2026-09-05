import pickle
import time
from pathlib import Path
import geopandas as gpd
import osmnx as ox
import pandas as pd
from urban_analysis.network import load_amenities_for_ward, load_network_for_ward
from urban_analysis.scoring import normalize_and_combine, score_all_points, score_all_points_fast
from urban_analysis.morphology import compute_intersection_share
from urban_analysis.wards import load_wards
from urban_analysis.config import CATEGORIES

RESULTS_PATH = Path("data/ward_results.csv")
CACHE_DIR = Path("data/ward_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 15

# ward numbers 91-100: a contiguous cluster in central Hyderabad
WARD_NUMBER_RANGE = range(91, 101)

def select_test_wards(wards: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    pattern = "|".join(f"Ward {n} " for n in WARD_NUMBER_RANGE)
    return wards[wards["Name"].str.contains(pattern, regex=True)]

def load_existing_results() -> pd.DataFrame:
    if RESULTS_PATH.exists():
        return pd.read_csv(RESULTS_PATH)
    columns = ["ward", "n_nodes", "n_amenities", "mean_access_index",
               "min_access_index", "max_access_index", "intersection_share", "status"]
    for cat in CATEGORIES:
        columns += [f"{cat}_bound_lo", f"{cat}_bound_hi"]
    return pd.DataFrame(columns=columns)

def successful_wards(df: pd.DataFrame) -> set:
    """Only wards that actually succeeded count as 'done' — a failed
    row should be retried on the next run, not skipped forever."""
    return set(df[df["status"] == "ok"]["ward"])

def append_result(row: dict):
    """Append one ward's result, replacing any old row for the same
    ward (e.g. a previous failed attempt) so retries don't duplicate."""
    if RESULTS_PATH.exists():
        existing = pd.read_csv(RESULTS_PATH)
        existing = existing[existing["ward"] != row["ward"]]
        existing = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        existing.to_csv(RESULTS_PATH, index=False)
    else:
        pd.DataFrame([row]).to_csv(RESULTS_PATH, index=False)

def process_one_ward(ward_row) -> dict:
    polygon = ward_row.geometry
    name = ward_row["Name"]
    safe_name = name.replace(" ", "_")

    G = load_network_for_ward(polygon)
    amenities = load_amenities_for_ward(polygon)
    amenities["nearest_node"] = amenities.geometry.apply(
        lambda pt: ox.distance.nearest_nodes(G, X=pt.x, Y=pt.y)
    )

    # cache the actual network + amenities (not just summary stats) —
    # this is what /simulate loads instead of re-parsing the 531MB PBF
    # on every request
    with open(CACHE_DIR / f"{safe_name}.pkl", "wb") as f:
        pickle.dump(G, f)
    amenities.to_file(CACHE_DIR / f"{safe_name}_amenities.geojson", driver="GeoJSON")

    # scores = score_all_points(list(G.nodes), G, amenities, categories=CATEGORIES)
    scores = score_all_points_fast(list(G.nodes), G, amenities, categories=CATEGORIES)
    scores = normalize_and_combine(scores, CATEGORIES)
    intersection_share = compute_intersection_share(G)

    result = {
        "ward": name,
        "n_nodes": G.number_of_nodes(),
        "n_amenities": len(amenities),
        "mean_access_index": scores["access_index"].mean(),
        "min_access_index": scores["access_index"].min(),
        "max_access_index": scores["access_index"].max(),
        "intersection_share": intersection_share,
        "status": "ok",
    }
    # per-category baseline bounds — the fixed scale /simulate normalizes
    # before/after against, so a genuine improvement stays visible
    for cat in CATEGORIES:
        result[f"{cat}_bound_lo"] = scores[cat].min()
        result[f"{cat}_bound_hi"] = scores[cat].max()

    return result

def process_with_retries(ward_row) -> dict:
    name = ward_row["Name"]
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return process_one_ward(ward_row)
        except Exception as e:
            last_error = e
            print(f"  attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    failed = {
        "ward": name, "n_nodes": None, "n_amenities": None,
        "mean_access_index": None, "min_access_index": None, "max_access_index": None,
        "intersection_share": None, "status": f"failed: {last_error}",
    }
    for cat in CATEGORIES:
        failed[f"{cat}_bound_lo"] = None
        failed[f"{cat}_bound_hi"] = None
    return failed

# Resumable by design: skips any ward already marked status="ok" in ward_results.csv, so this can be safely 
# re-run after an interruption without reprocessing everything. 
# Deleting/renaming ward_results.csv forces a full rerun (needed after a scoring/category schema change).

def main():
    wards = load_wards("data/wards_hyderabad.geojson")
    print(f"total wards in dataset: {len(wards)}")

    already_done = successful_wards(load_existing_results())
    remaining = wards[~wards["Name"].isin(already_done)]
    print(f"{len(already_done)} succeeded already, {len(remaining)} to (re)try")

    for i, (_, ward_row) in enumerate(remaining.iterrows(), 1):
        name = ward_row["Name"]
        print(f"[{i}/{len(remaining)}] processing {name}...")
        result = process_with_retries(ward_row)
        append_result(result)

        if result["status"] == "ok":
            print(f"  done: mean access_index = {result['mean_access_index']:.1f}")
        else:
            print(f"  FAILED permanently: {result['status']}")

if __name__ == "__main__":
    main()