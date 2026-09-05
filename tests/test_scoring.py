import networkx as nx
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from urban_analysis.scoring import (
    normalize_with_fixed_bounds,
    score_all_points,
    score_all_points_fast,
)

def make_line_graph(n_nodes=5, travel_time_per_edge=300):
    G = nx.Graph()
    for i in range(n_nodes):
        G.add_node(i, x=float(i), y=0.0)
    for i in range(n_nodes - 1):
        G.add_edge(i, i + 1, travel_time=travel_time_per_edge)
    return G

class TestNormalizeWithFixedBounds:
    def test_normal_range_scales_correctly(self):
        df = pd.DataFrame({"hospital": [0, 5, 10]})
        bounds = {"hospital": (0, 10)}
        result = normalize_with_fixed_bounds(df, ["hospital"], bounds)
        assert result["hospital_norm"].tolist() == [0.0, 50.0, 100.0]

    def test_degenerate_range_zero_count_stays_zero(self):
        df = pd.DataFrame({"pharmacy": [0]})
        bounds = {"pharmacy": (0, 0)}
        result = normalize_with_fixed_bounds(df, ["pharmacy"], bounds)
        assert result["pharmacy_norm"].iloc[0] == 0.0

    def test_degenerate_range_any_increase_maps_to_max(self):
        df = pd.DataFrame({"pharmacy": [0, 1, 3]})
        bounds = {"pharmacy": (0, 0)}
        result = normalize_with_fixed_bounds(df, ["pharmacy"], bounds)
        assert result["pharmacy_norm"].tolist() == [0.0, 100.0, 100.0]

    def test_value_above_historical_bound_is_clipped_not_over_100(self):
        df = pd.DataFrame({"school": [15]})
        bounds = {"school": (0, 10)}
        result = normalize_with_fixed_bounds(df, ["school"], bounds)
        assert result["school_norm"].iloc[0] == 100.0

    def test_access_index_is_mean_of_normalized_categories(self):
        df = pd.DataFrame({"school": [10], "park": [0]})
        bounds = {"school": (0, 10), "park": (0, 10)}
        result = normalize_with_fixed_bounds(df, ["school", "park"], bounds)
        assert result["access_index"].iloc[0] == 50.0  # mean(100, 0)

class TestScoreAllPointsEquivalence:

    def test_fast_and_original_agree_on_synthetic_graph(self):
        G = make_line_graph(n_nodes=5, travel_time_per_edge=300)  # 5 min/edge
        amenities = gpd.GeoDataFrame({
            "category": ["hospital", "school"],
            "nearest_node": [0, 4],
            "geometry": [Point(0, 0), Point(4, 0)],
        })
        categories = ["hospital", "school"]

        original = score_all_points(
            list(G.nodes), G, amenities, categories=categories,
        ).set_index("node").sort_index()
        fast = score_all_points_fast(
            list(G.nodes), G, amenities, categories=categories,
        ).set_index("node").sort_index()

        pd.testing.assert_frame_equal(
            original[categories].astype(float),
            fast[categories].astype(float),
        )

    def test_amenity_outside_cutoff_not_counted(self):
        G = make_line_graph(n_nodes=5, travel_time_per_edge=300)
        amenities = gpd.GeoDataFrame({
            "category": ["hospital"],
            "nearest_node": [4],
            "geometry": [Point(4, 0)],
        })
        result = score_all_points_fast(
            list(G.nodes), G, amenities, categories=["hospital"],
        ).set_index("node")
        assert result.loc[0, "hospital"] == 0
        assert result.loc[4, "hospital"] == 1  # amenity's own node