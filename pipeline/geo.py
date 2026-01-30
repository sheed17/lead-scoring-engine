"""
Geographic utilities for grid-based search coverage.

This module generates a grid of lat/lng points to ensure complete coverage
of a city area when using radius-based searches.
"""

import math
from typing import List, Tuple

# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.
    
    Args:
        lat1, lng1: First point coordinates in degrees
        lat2, lng2: Second point coordinates in degrees
    
    Returns:
        Distance in kilometers
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return EARTH_RADIUS_KM * c


def km_to_degrees_lat(km: float) -> float:
    """Convert kilometers to degrees latitude (approximately constant)."""
    return km / 111.0


def km_to_degrees_lng(km: float, latitude: float) -> float:
    """
    Convert kilometers to degrees longitude at a given latitude.
    Longitude degrees get smaller as you move toward the poles.
    """
    return km / (111.0 * math.cos(math.radians(latitude)))


def generate_geo_grid(
    city_center_lat: float,
    city_center_lng: float,
    city_radius_km: float,
    search_radius_km: float = 1.5
) -> List[Tuple[float, float, int]]:
    """
    Generate a grid of lat/lng points to cover a circular city area.
    
    Uses overlapping circles to ensure no gaps in coverage. The search radius
    determines how fine-grained the grid is.
    
    Args:
        city_center_lat: Latitude of city center
        city_center_lng: Longitude of city center
        city_radius_km: Radius of city area to cover (in km)
        search_radius_km: Radius for each search point (in km, default 1.5km)
                         Smaller = more coverage but more API calls
    
    Returns:
        List of (lat, lng, radius_meters) tuples for each grid point
    """
    grid_points = []
    
    # Use ~70% of search radius as step size to ensure overlap
    # This prevents gaps between circular search areas
    step_km = search_radius_km * 1.4  # √2 ≈ 1.414 for diagonal coverage
    
    # Convert to degrees
    step_lat = km_to_degrees_lat(step_km)
    step_lng = km_to_degrees_lng(step_km, city_center_lat)
    
    # Calculate grid bounds
    lat_range = km_to_degrees_lat(city_radius_km)
    lng_range = km_to_degrees_lng(city_radius_km, city_center_lat)
    
    # Generate grid points within the city radius
    lat = city_center_lat - lat_range
    while lat <= city_center_lat + lat_range:
        lng = city_center_lng - lng_range
        while lng <= city_center_lng + lng_range:
            # Check if this point is within the city radius
            distance = haversine_distance(city_center_lat, city_center_lng, lat, lng)
            if distance <= city_radius_km:
                # Convert search radius to meters for API
                radius_m = int(search_radius_km * 1000)
                grid_points.append((lat, lng, radius_m))
            lng += step_lng
        lat += step_lat
    
    return grid_points


def estimate_api_calls(
    city_radius_km: float,
    search_radius_km: float = 1.5,
    keywords_count: int = 1,
    max_pages: int = 3
) -> dict:
    """
    Estimate the number of API calls for a given search configuration.
    
    Useful for cost estimation before running a large extraction.
    
    Args:
        city_radius_km: Radius of city area to cover
        search_radius_km: Radius for each search point
        keywords_count: Number of keyword variations to search
        max_pages: Maximum pages per query (up to 3)
    
    Returns:
        Dictionary with estimation details
    """
    # Generate grid to count points
    grid = generate_geo_grid(0, 0, city_radius_km, search_radius_km)
    grid_points = len(grid)
    
    # Each grid point × each keyword = base queries
    base_queries = grid_points * keywords_count
    
    # Each query can have up to max_pages (pagination)
    max_total_calls = base_queries * max_pages
    
    # Estimate results (20 per page, 60 max per query)
    max_results_per_query = 20 * max_pages
    theoretical_max_results = base_queries * max_results_per_query
    
    return {
        "grid_points": grid_points,
        "keywords": keywords_count,
        "base_queries": base_queries,
        "max_api_calls": max_total_calls,
        "max_results_theoretical": theoretical_max_results,
        "note": "Actual results will be lower due to deduplication and sparse areas"
    }
