import networkx as nx
import pandas as pd
from urban_analysis.config import TIME_CUTOFF_SECONDS
from urban_analysis.config import CATEGORIES

def score_point(node, G, amenities: pd.DataFrame) -> dict:
    reachable = nx.single_source_dijkstra_path_length(
        G, node, cutoff=TIME_CUTOFF_SECONDS, weight="travel_time"
    )
    reachable_mask = amenities["nearest_node"].isin(reachable.keys())
    counts = amenities[reachable_mask].groupby("category").size()

    row = {"node": node}
    row.update(counts.to_dict())
    return row

def score_all_points(nodes, G, amenities, categories=CATEGORIES):
    rows = [score_point(node, G, amenities) for node in nodes]
    df = pd.DataFrame(rows).fillna(0)

    # a category with zero amenities anywhere in the ward never appears as
    # a key in any row's dict, so the column itself is missing — reindex
    # to guarantee every expected category column exists, filled with 0
    for cat in categories:
        if cat not in df.columns:
            df[cat] = 0.0

    return df
# Same output as score_all_points, but loops over amenities insteadof nodes. Faster whenever 
# n_amenities << n_nodes (the common case — e.g. 63 amenities vs 2891 nodes in Ward 91 Khairatabad).
def score_all_points_fast(nodes, G, amenities, categories):
    node_set = set(nodes) 
    counts = {n: {cat: 0 for cat in categories} for n in node_set}

    for cat in categories:
        cat_amenities = amenities[amenities["category"] == cat]
        for _, row in cat_amenities.iterrows():
            source = row["nearest_node"]
            if source not in G:
                continue
            reachable = nx.single_source_dijkstra_path_length(
                G, source, cutoff=TIME_CUTOFF_SECONDS, weight="travel_time"
            )
            for n in reachable:
                if n in node_set:
                    counts[n][cat] += 1

    df = pd.DataFrame([{"node": n, **counts[n]} for n in node_set]).fillna(0)
    df = df.reindex(columns=["node"] + list(categories), fill_value=0)
    return df

def normalize_and_combine(scores_df: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    result = scores_df.copy()
    norm_cols = []

    for cat in categories:
        lo, hi = scores_df[cat].min(), scores_df[cat].max()
        norm_col = f"{cat}_norm"
        result[norm_col] = 0.0 if hi == lo else (scores_df[cat] - lo) / (hi - lo) * 100
        norm_cols.append(norm_col)

    result["access_index"] = result[norm_cols].mean(axis=1)
    return result

def normalize_with_fixed_bounds(scores_df, categories, bounds):
    result = scores_df.copy()
    norm_cols = []
    for cat in categories:
        lo, hi = bounds[cat]
        norm_col = f"{cat}_norm"
        if hi == lo:
            # Degenerate range: this ward had zero variation in this category across all its nodes 
            # (e.g. every node reachable at most 0 pharmacies). Any count above that flat value is a real 
            # improvement, not "no change" — must NOT collapse to a flat 0, or hypothetical-amenity 
            # simulations for under-served categories always show zero effect.
            
            result[norm_col] = (scores_df[cat] > lo).astype(float) * 100
        else:
            result[norm_col] = ((scores_df[cat] - lo) / (hi - lo) * 100).clip(0, 100)
        norm_cols.append(norm_col)
    result["access_index"] = result[norm_cols].mean(axis=1)
    return result