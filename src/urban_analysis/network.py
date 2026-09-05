import geopandas as gpd
import pandas as pd
import osmnx as ox

from urban_analysis.config import AMENITY_TAGS

def load_network(place: str, dist: int = 1000):
    from urban_analysis.config import WALK_SPEED_MPS

    G = ox.graph_from_address(place, dist=dist, network_type="walk")

    for u, v, data in G.edges(data=True):
        data["travel_time"] = data["length"] / WALK_SPEED_MPS

    return G

# Fetch schools/hospitals/parks/groceries near `place`, unified into one GeoDataFrame with a 'category' column, 
# one Point per amenity.
    
def load_amenities(place: str, dist: int = 1000) -> gpd.GeoDataFrame:

    combined = []
    for category, tags in AMENITY_TAGS.items():
        gdf = ox.features_from_address(place, tags=tags, dist=dist)
        gdf = gdf[["geometry"]].copy()
        gdf["geometry"] = gdf.geometry.centroid  # polygons -> points
        gdf["category"] = category
        combined.append(gdf)

    return gpd.GeoDataFrame(pd.concat(combined, ignore_index=True), crs="EPSG:4326")

def snap_amenities_to_network(amenities: gpd.GeoDataFrame, G) -> gpd.GeoDataFrame:

    amenities = amenities.copy()
    amenities["nearest_node"] = amenities.geometry.apply(
        lambda point: ox.distance.nearest_nodes(G, X=point.x, Y=point.y)
    )
    return amenities

def load_network_for_ward(ward_polygon, pbf_path="data/southern-zone.osm.pbf"):
 
    from pyrosm import OSM
    from urban_analysis.config import WALK_SPEED_MPS

    osm = OSM(pbf_path, bounding_box=ward_polygon)
    nodes, edges = osm.get_network(network_type="walking", nodes=True)
    G = osm.to_graph(nodes, edges, graph_type="networkx")

    for u, v, data in G.edges(data=True):
        data["travel_time"] = data["length"] / WALK_SPEED_MPS

    return G

def load_amenities_for_ward(ward_polygon, pbf_path="data/southern-zone.osm.pbf"):
    from pyrosm import OSM
    import geopandas as gpd

    osm = OSM(pbf_path, bounding_box=ward_polygon)
    custom_filter = {
        "amenity": ["school", "hospital", "clinic", "doctors", "dentist",
                    "health_post", "nursing_home", "pharmacy"],
        "leisure": ["park"],
        "shop": ["supermarket", "convenience"],
    }

    # pyrosm returns None (not an empty GeoDataFrame) when nothing matches — this ward can legitimately have zero qualifying a
    pois = osm.get_pois(custom_filter=custom_filter)

    if pois is None:
        return gpd.GeoDataFrame(
            columns=["geometry", "category"], geometry="geometry", crs="EPSG:4326"
        )

    HOSPITAL_FAMILY = {"hospital", "clinic", "doctors", "dentist",
                        "health_post", "nursing_home"}

    def infer_category(row):
        if row.get("amenity") == "school":
            return "school"
        if row.get("amenity") in HOSPITAL_FAMILY:
            return "hospital"
        if row.get("amenity") == "pharmacy":
            return "pharmacy"
        if row.get("leisure") == "park":
            return "park"
        if row.get("shop") in ("supermarket", "convenience"):
            return "grocery"
        return None

    pois["category"] = pois.apply(infer_category, axis=1)
    pois = pois[pois["category"].notna()].copy()
    pois["geometry"] = pois.geometry.centroid
    return gpd.GeoDataFrame(pois[["geometry", "category"]].reset_index(drop=True), crs="EPSG:4326")

def add_hypothetical_amenity(amenities, lon, lat, category, G):

    import geopandas as gpd
    from shapely.geometry import Point
    import osmnx as ox

    new_node = ox.distance.nearest_nodes(G, X=lon, Y=lat)
    new_row = gpd.GeoDataFrame(
        [{"geometry": Point(lon, lat), "category": category, "nearest_node": new_node}],
        crs=amenities.crs,
    )
    return gpd.pd.concat([amenities, new_row], ignore_index=True)