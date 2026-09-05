# wards_hyderabad.geojson (sourced from bharatlas.com) stores coordinates as (lat, lon) instead of standard 
# (lon, lat) — a quirk from its KML-to-GeoJSON conversion pipeline. This function swaps them back.
# Always load wards through this function, never gpd.read_file() directly,
# or every downstream geometry operation will be silently wrong.

import geopandas as gpd
from shapely.ops import transform

def load_wards(path: str) -> gpd.GeoDataFrame:
    wards = gpd.read_file(path)
    wards["geometry"] = wards["geometry"].apply(
        lambda geom: transform(lambda x, y, z=None: (y, x), geom)
    )
    return wards