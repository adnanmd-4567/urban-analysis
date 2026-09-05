WALK_SPEED_KMH = 4.8          # average adult walking speed
TIME_CUTOFF_MINUTES = 15      # the "15-minute city" threshold

WALK_SPEED_MPS = WALK_SPEED_KMH * 1000 / 3600
TIME_CUTOFF_SECONDS = TIME_CUTOFF_MINUTES * 60

# Single source of truth for category names

CATEGORIES = ["grocery", "hospital", "pharmacy", "park", "school"]

# Category definitions for the 15-minute access model. "hospital" is intentionally broad — it includes clinics, 
# doctors, dentists, health posts, and nursing homes, not just amenity=hospital, since a narrow definition 
# undercounted real healthcare access by ~45% in this dataset.

AMENITY_TAGS = {
    "school": {"amenity": "school"},
    "hospital": {"amenity": ["hospital", "clinic", "doctors", "dentist",
                              "health_post", "nursing_home"]},
    "pharmacy": {"amenity": "pharmacy"},
    "park": {"leisure": "park"},
    "grocery": {"shop": ["supermarket", "convenience"]},
}