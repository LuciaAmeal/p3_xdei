"""Utilities for the dynamic vehicle simulator.

Lightweight geospatial helpers (haversine/interpolation) and GTFS helpers
used by the simulator.
"""
from __future__ import annotations

from typing import List, Tuple
import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two lat/lon points using Haversine."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def cumulative_distances(coords: List[Tuple[float, float]]) -> List[float]:
    """Given a list of (lon, lat) coordinates return cumulative distances (meters).

    Returns list with same length where first element is 0.0
    """
    dists = [0.0]
    for i in range(1, len(coords)):
        lon1, lat1 = coords[i-1]
        lon2, lat2 = coords[i]
        d = haversine(lat1, lon1, lat2, lon2)
        dists.append(dists[-1] + d)
    return dists


def interpolate_along_line(coords: List[Tuple[float, float]], distance_m: float) -> Tuple[float, float]:
    """Interpolate a point at `distance_m` meters along the polyline `coords`.

    Coordinates are list of (lon, lat). Returns (lon, lat).
    If distance_m <= 0 returns first point; if >= total length returns last point.
    """
    if not coords:
        raise ValueError("coords must contain at least one point")
    if len(coords) == 1:
        return coords[0]

    cum = cumulative_distances(coords)
    total = cum[-1]
    if distance_m <= 0 or total == 0:
        return coords[0]
    if distance_m >= total:
        return coords[-1]

    # find segment
    for i in range(1, len(cum)):
        if cum[i] >= distance_m:
            seg_start = cum[i-1]
            seg_end = cum[i]
            frac = (distance_m - seg_start) / (seg_end - seg_start) if seg_end > seg_start else 0.0
            lon1, lat1 = coords[i-1]
            lon2, lat2 = coords[i]
            lon = lon1 + (lon2 - lon1) * frac
            lat = lat1 + (lat2 - lat1) * frac
            return (lon, lat)

    return coords[-1]


def parse_time_to_seconds(timestr: str) -> int:
    """Parse HH:MM:SS (or H:MM:SS) into seconds since midnight."""
    parts = timestr.split(":")
    if len(parts) != 3:
        raise ValueError("time string must be HH:MM:SS")
    h, m, s = (int(p) for p in parts)
    return h * 3600 + m * 60 + s


def trip_duration_seconds(stop_times: List[dict]) -> int:
    """Return duration in seconds for a trip using first departure to last arrival."""
    if not stop_times:
        return 0
    first = stop_times[0].get("departure_time") or stop_times[0].get("arrival_time")
    last = stop_times[-1].get("arrival_time") or stop_times[-1].get("departure_time")
    return max(0, parse_time_to_seconds(last) - parse_time_to_seconds(first))
