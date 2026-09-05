from unittest.mock import patch, MagicMock
import geopandas as gpd
from shapely.geometry import Polygon
from urban_analysis.network import load_amenities_for_ward

def test_load_amenities_returns_empty_gdf_when_pyrosm_returns_none():
    fake_polygon = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])

    with patch("pyrosm.OSM") as MockOSM:
        mock_instance = MagicMock()
        mock_instance.get_pois.return_value = None
        MockOSM.return_value = mock_instance

        result = load_amenities_for_ward(fake_polygon, pbf_path="fake.pbf")

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0
    assert "category" in result.columns

def test_healthcare_family_maps_to_hospital_category():
    import pandas as pd

    fake_polygon = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    fake_pois = gpd.GeoDataFrame({
        "amenity": ["hospital", "clinic", "doctors", "dentist",
                    "health_post", "nursing_home", "pharmacy", "school"],
        "geometry": [Polygon([(0, 0), (0, 0.1), (0.1, 0.1), (0.1, 0)])] * 8,
    }, crs="EPSG:4326")

    with patch("pyrosm.OSM") as MockOSM:
        mock_instance = MagicMock()
        mock_instance.get_pois.return_value = fake_pois
        MockOSM.return_value = mock_instance

        result = load_amenities_for_ward(fake_polygon, pbf_path="fake.pbf")

    counts = result["category"].value_counts()
    assert counts.get("hospital", 0) == 6  # everything except pharmacy/school
    assert counts.get("pharmacy", 0) == 1
    assert counts.get("school", 0) == 1