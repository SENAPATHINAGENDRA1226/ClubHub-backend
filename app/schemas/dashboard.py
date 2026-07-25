from typing import Any, Dict, List
from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    month: str
    value: int


class BarChartPoint(BaseModel):
    label: str
    value: int


class StudentDashboardResponse(BaseModel):
    total_events: int
    active_members_count: int
    active_committees_count: int
    my_registrations_count: int
    quick_links: List[Dict[str, Any]]


class AdminDashboardResponse(BaseModel):
    total_events: int
    total_members: int
    total_alumni: int
    upcoming_events_count: int
    registrations_over_time: List[TimeSeriesPoint]
    most_popular_events: List[BarChartPoint]
