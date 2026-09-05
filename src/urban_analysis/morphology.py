import geopandas as gpd
import momepy
import pandas as pd
from shapely.geometry import LineString

def graph_to_undirected_edges_gdf(G, crs="EPSG:4326") -> gpd.GeoDataFrame:
    seen = set()
    records = []
    for u, v, data in G.edges(data=True):
        key = tuple(sorted([u, v]))
        if key in seen:
            continue
        seen.add(key)

        u_data, v_data = G.nodes[u], G.nodes[v]
        records.append({
            "geometry": LineString([(u_data["x"], u_data["y"]), (v_data["x"], v_data["y"])]),
            "length": data.get("length"),
        })
    if not records:
        return gpd.GeoDataFrame(columns=["geometry", "length"], geometry="geometry", crs=crs)
    return gpd.GeoDataFrame(records, crs=crs)

# Percent of network nodes that are real intersections (degree 3+), a proxy for how well-connected/walkable  the street grid is.

def compute_intersection_share(G, geographic_crs="EPSG:4326", projected_crs="EPSG:32644") -> float:

    edges = graph_to_undirected_edges_gdf(G, crs=geographic_crs)
    edges_proj = edges.to_crs(projected_crs)
    morph_graph = momepy.gdf_to_nx(edges_proj)
    morph_graph = momepy.node_degree(morph_graph)
    nodes_gdf, _ = momepy.nx_to_gdf(morph_graph)

    return (nodes_gdf["degree"] >= 3).mean() * 100