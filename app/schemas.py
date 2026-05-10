"""
app/schemas.py – Pydantic request/response models
"""

from pydantic import BaseModel, Field
from typing import Optional


class GeoResponse(BaseModel):
    ip:           str
    country:      Optional[str]   = None
    country_code: Optional[str]   = None
    continent:    Optional[str]   = None
    region:       Optional[str]   = None
    region_code:  Optional[str]   = None
    city:         Optional[str]   = None
    postal_code:  Optional[str]   = None
    latitude:     Optional[float] = None
    longitude:    Optional[float] = None
    accuracy_km:  Optional[int]   = None
    timezone:     Optional[str]   = None
    note:         Optional[str]   = None
    error:        Optional[str]   = None

    model_config = {"json_schema_extra": {"example": {
        "ip": "8.8.8.8",
        "country": "United States",
        "country_code": "US",
        "continent": "North America",
        "region": "Virginia",
        "region_code": "VA",
        "city": "Ashburn",
        "postal_code": "20146",
        "latitude": 37.751,
        "longitude": -97.822,
        "accuracy_km": 1000,
        "timezone": "America/Chicago",
        "note": None,
        "error": None,
    }}}


class BatchRequest(BaseModel):
    targets: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of IPs or hostnames (max 100 per request)",
        examples=[["8.8.8.8", "1.1.1.1", "google.com"]],
    )


class BatchResponse(BaseModel):
    count:   int
    results: list[GeoResponse]


class HealthResponse(BaseModel):
    status:   str
    database: str
    version:  str


class MyIPResponse(BaseModel):
    public_ip: str
    geo:       GeoResponse
