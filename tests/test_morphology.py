import networkx as nx

from urban_analysis.morphology import graph_to_undirected_edges_gdf

def make_directed_square():
    G = nx.MultiDiGraph()
    coords = {0: (0, 0), 1: (1, 0), 2: (1, 1), 3: (0, 1)}
    for node, (x, y) in coords.items():
        G.add_node(node, x=x, y=y)
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 0)]:
        G.add_edge(u, v, length=10.0)
        G.add_edge(v, u, length=10.0)  # reciprocal, as osmnx does for two-way streets
    return G

class TestGraphToEdgesGdf:
    def test_reciprocal_edges_are_not_double_counted(self):
        G = make_directed_square()
        assert G.number_of_edges() == 8
        edges_gdf = graph_to_undirected_edges_gdf(G)
        assert len(edges_gdf) == 4

    def test_edge_geometry_has_two_points(self):
        G = make_directed_square()
        edges_gdf = graph_to_undirected_edges_gdf(G)
        assert all(len(list(geom.coords)) == 2 for geom in edges_gdf.geometry)

    def test_isolated_node_does_not_crash(self):
        G = nx.MultiDiGraph()
        G.add_node(0, x=0.0, y=0.0)  # no edges at all
        edges_gdf = graph_to_undirected_edges_gdf(G)
        assert len(edges_gdf) == 0

    def test_one_way_street_still_produces_one_segment(self):
        G = nx.MultiDiGraph()
        G.add_node(0, x=0.0, y=0.0)
        G.add_node(1, x=1.0, y=0.0)
        G.add_edge(0, 1, length=10.0)  # one direction only
        edges_gdf = graph_to_undirected_edges_gdf(G)
        assert len(edges_gdf) == 1