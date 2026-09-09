from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forecasting.predict import predict_shortage
from redistribution.redistribute import run_redistribution
from routing.route_optimizer import get_route_plan

app = FastAPI(title="HemoLynk ML API")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(BASE_DIR, "..", "data")

@app.get("/")
def root():
    return {"status": "HemoLynk ML API is running"}

# ── Forecast Endpoint ──────────────────────────────────────────────

class ForecastRequest(BaseModel):
    facility_id: str
    facility_type: str
    blood_group: str
    recent_usage_7d: List[float]
    recent_usage_30d: List[float]
    current_stock_units: float
    target_date: Optional[date] = None

@app.post("/forecast")
def forecast(req: ForecastRequest):
    result = predict_shortage(
        facility_id         = req.facility_id,
        facility_type       = req.facility_type,
        blood_group         = req.blood_group,
        recent_usage_7d     = req.recent_usage_7d,
        recent_usage_30d    = req.recent_usage_30d,
        current_stock_units = req.current_stock_units,
        target_date         = req.target_date
    )
    result["shortage_risk"] = bool(result["shortage_risk"])
    return result

# ── Redistribution Endpoint ────────────────────────────────────────

@app.post("/redistribute")
def redistribute():
    inventory_df  = pd.read_csv(os.path.join(DATA_DIR, "inventory.csv"))
    facilities_df = pd.read_csv(os.path.join(DATA_DIR, "facilities.csv"))

    transfers, admin_flags, reassignments = run_redistribution(
        inventory_df, facilities_df)

    return {
        "total_transfers"    : len(transfers),
        "total_admin_flags"  : len(admin_flags),
        "total_reassignments": len(reassignments),
        "transfers"          : transfers,
        "admin_flags"        : admin_flags,
        "reassignments"      : reassignments
    }

# ── Route Endpoint ─────────────────────────────────────────────────

class RouteRequest(BaseModel):
    source_id: str
    target_id: str

@app.post("/route")
def route(req: RouteRequest):
    facilities_df = pd.read_csv(os.path.join(DATA_DIR, "facilities.csv"))
    result = get_route_plan(facilities_df, req.source_id, req.target_id)
    return result