from pydantic import BaseModel

class SimulationRequest(BaseModel):
    lon: float
    lat: float
    category: str  # one of: school, hospital, park, grocery

class SimulationResult(BaseModel):
    ward: str
    category: str
    access_index_before: float
    access_index_after: float
    delta: float
    category_count_before: float
    category_count_after: float
    already_exists_nearby: bool