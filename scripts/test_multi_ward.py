"""Small-scale pipeline test on a handful of wards — a fast, cheap sanity check before committing to a long run 
of build_all_wards.py across all 145 wards.

This was the first script used to validate the full pipeline (network fetch, amenity snapping, scoring, normalization) 
end-to-end on real ward polygon data, before the more resilient production version (build_all_wards.py) existed. 
It deliberately has NO retry logic, no disk caching between wards, and no resume-from-failure support — any
single ward failing just gets logged and skipped, and a re-run starts over from scratch every time.

Kept in the repo as a lightweight, disposable smoke test: useful for quickly confirming the pipeline still works 
on a small sample (e.g. after changing scoring.py or network.py) without waiting for a full 145-ward run. 
For the actual production data-generation pipeline — with retries, caching, and resumability — see build_all_wards.py
instead.

Usage:
    python scripts/test_multi_ward.py
"""

import pandas as pd

from urban_analysis.network import load_network_for_ward, load_amenities_for_ward
from urban_analysis.scoring import score_all_points, normalize_and_combine
from urban_analysis.wards import load_wards
from urban_analysis.config import CATEGORIES

TEST_WARD_NAMES = [
    "Banjara Hills",
    "Jubilee Hills",
    "Khairatabad",
    "Somajiguda",
]

def process_one_ward(ward_row):
    polygon = ward_row.geometry
    name = ward_row["Name"]

    G = load_network_for_ward(polygon)
    amenities = load_amenities_for_ward(polygon)
    amenities["nearest_node"] = amenities.geometry.apply(
        lambda pt: __import__("osmnx").distance.nearest_nodes(G, X=pt.x, Y=pt.y)
    )

    scores = score_all_points(list(G.nodes), G, amenities)
    scores = normalize_and_combine(scores, CATEGORIES)

    return {
        "ward": name,
        "n_nodes": G.number_of_nodes(),
        "n_amenities": len(amenities),
        "mean_access_index": scores["access_index"].mean(),
        "min_access_index": scores["access_index"].min(),
        "max_access_index": scores["access_index"].max(),
    }

# NOTE: unlike build_all_wards.py, there is no caching or skip-already- done logic here — every run reprocesses 
# every ward from scratch, and a failure here is silently thrown away on the next run. 
# That's a deliberate simplicity trade-off for a quick smoke test, not something to fix — use build_all_wards.py 
# for anything that needs to survive interruption or scale to many wards.

def main():
    wards = load_wards("data/wards_hyderabad.geojson")
    results = []
    failures = []

    for name in TEST_WARD_NAMES:
        match = wards[wards["Name"].str.contains(name)]
        if match.empty:
            failures.append((name, "not found in ward dataset"))
            continue

        print(f"processing {name}...")
        try:
            result = process_one_ward(match.iloc[0])
            results.append(result)
            print(f"  done: mean access_index = {result['mean_access_index']:.1f}")
        except Exception as e:
            print(f"  FAILED: {e}")
            failures.append((name, str(e)))

    summary = pd.DataFrame(results)
    print("\n=== Summary ===")
    print(summary)

    if failures:
        print("\n=== Failures ===")
        for name, reason in failures:
            print(f"  {name}: {reason}")

if __name__ == "__main__":
    main()