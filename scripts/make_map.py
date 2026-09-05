"""Generate a static, standalone folium map from the precomputed ward scores — a lightweight way to sanity-check 
the data (access index, hotspot classification) visually without running the full FastAPI + Leaflet frontend.

This script is a development/debugging tool, not part of the deployed product: the live project's actual map 
is the Leaflet frontend in frontend/index.html, which fetches live from the FastAPI /wards endpoint. 
This script instead reads data/ward_scores_final.geojson directly and writes a one-off HTML file 
(frontend/access_map.html) — useful for quickly eyeballing a new batch of ward results after a
build_all_wards.py run, before wiring them into the live frontend.

frontend/access_map.html is intentionally NOT committed to the repo: it's a disposable artifact regenerated on 
demand by this script, and it only ever reflects however many wards had been processed at the time it was last 
run (currently a subset, not all 145) — committing a stale, partial version would be misleading. 
Run this script yourself to regenerate a current one locally.

Usage:
    python scripts/make_map.py
"""

import folium
import geopandas as gpd

wards = gpd.read_file("data/ward_scores_final.geojson")

# reproject to a metric CRS (UTM 44N covers Hyderabad) before computing centroids — computing centroid directly 
# on lat/lon geometry triggers a UserWarning and is technically inaccurate, since degrees aren't a constant 
# real-world distance (a fix we learned the hard way earlier in this project's development)

wards_proj = wards.to_crs("EPSG:32644")
center = [wards_proj.geometry.centroid.to_crs(wards.crs).y.mean(),
          wards_proj.geometry.centroid.to_crs(wards.crs).x.mean()]

m = folium.Map(location=center, zoom_start=13, tiles="cartodbpositron")

# layer 1: smooth color gradient by composite access_index — the "what can residents reach" view
folium.Choropleth(
    geo_data=wards,
    data=wards,
    columns=["Name", "mean_access_index"],
    key_on="feature.properties.Name",
    fill_color="RdYlGn",
    fill_opacity=0.7,
    line_opacity=0.4,
    legend_name="Mean Access Index (0-100)",
    name="Access Index",
).add_to(m)

# layer 2: hotspot classification, distinct colors per category
# folium.GeoJson with a style_function does NOT auto-generate a legend (unlike folium.Choropleth, which does) — 
# the manual legend_html block below exists specifically to cover that gap.
hotspot_colors = {
    "High-High": "#d73027",
    "Low-Low": "#4575b4",
    "High-Low": "#fdae61",
    "Low-High": "#abd9e9",
    "Not significant": "#cccccc",
}

def style_hotspot(feature):
    label = feature["properties"]["hotspot_label"]
    return {"fillColor": hotspot_colors.get(label, "#cccccc"), "color": "black",
            "weight": 1, "fillOpacity": 0.6}

folium.GeoJson(
    wards,
    style_function=style_hotspot,
    tooltip=folium.GeoJsonTooltip(
        fields=["Name", "mean_access_index", "hotspot_label", "intersection_share"],
        aliases=["Ward", "Access Index", "Hotspot", "Intersection %"],
        localize=True,
    ),
    name="Hotspots",
).add_to(m)

legend_html = """
<div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
            background: white; padding: 10px 14px; border-radius: 6px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-size: 13px; line-height: 1.6;">
    <b>Hotspot Type</b><br>
    <span style="background:#d73027;width:12px;height:12px;display:inline-block;margin-right:6px;"></span>High-High — well-served cluster<br>
    <span style="background:#4575b4;width:12px;height:12px;display:inline-block;margin-right:6px;"></span>Low-Low — underserved cluster<br>
    <span style="background:#fdae61;width:12px;height:12px;display:inline-block;margin-right:6px;"></span>High-Low — outlier (good, poor neighbors)<br>
    <span style="background:#abd9e9;width:12px;height:12px;display:inline-block;margin-right:6px;"></span>Low-High — outlier (poor, good neighbors)<br>
    <span style="background:#cccccc;width:12px;height:12px;display:inline-block;margin-right:6px;"></span>Not significant
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

folium.LayerControl().add_to(m)

folium.LayerControl().add_to(m)

m.save("frontend/access_map.html")
print("saved -> frontend/access_map.html")