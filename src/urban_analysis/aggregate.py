import geopandas as gpd
import pandas as pd

def nodes_to_gdf(G) -> gpd.GeoDataFrame:
    records = [
        {"node": n, "geometry": gpd.points_from_xy([d["x"]], [d["y"]])[0]}
        for n, d in G.nodes(data=True)
    ]
    return gpd.GeoDataFrame(records, crs="EPSG:4326")

def join_scores_to_wards(
    scores_df: pd.DataFrame,
    nodes_gdf: gpd.GeoDataFrame,
    wards: gpd.GeoDataFrame,
    value_cols: list[str],
    ward_id_col: str = "Name",
) -> gpd.GeoDataFrame:
    
    # Spatially join scored nodes into their containing ward, then average each score column per ward. 
    # Nodes outside every ward (e.g. a test circle spilling past a ward boundary) are dropped —
    # predicate='within' only keeps nodes strictly inside a polygon.
    
    merged = nodes_gdf.merge(scores_df, on="node")
    joined = gpd.sjoin(merged, wards[[ward_id_col, "geometry"]], how="inner", predicate="within")
    ward_means = joined.groupby(ward_id_col)[value_cols].mean().reset_index()
    return wards.merge(ward_means, on=ward_id_col, how="left")