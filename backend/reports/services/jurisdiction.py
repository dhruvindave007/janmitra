"""
JurisdictionService: GPS-based police station routing.

Finds nearest police station using haversine distance formula.
Pure deterministic logic, no AI/ML involved.

Usage:
    from reports.services import JurisdictionService
    
    # Find nearest station to incident location
    station = JurisdictionService.find_nearest_station(lat, lon)
    
    # Find nearest station in a specific state
    station = JurisdictionService.find_nearest_station(lat, lon, state='Maharashtra')
"""

import math
from decimal import Decimal
from typing import Optional, Tuple

from django.db.models import QuerySet

from core.models import PoliceStation


class JurisdictionService:
    """
    Service for GPS-based police station routing.
    
    Uses haversine formula to calculate great-circle distance
    between two GPS coordinates on Earth's surface.
    
    All distances are in kilometers.
    """
    
    # Earth's radius in kilometers
    EARTH_RADIUS_KM = 6371.0
    
    # Maximum reasonable distance for routing (500km - beyond this, something is wrong)
    MAX_ROUTING_DISTANCE_KM = 500.0
    
    @classmethod
    def _to_radians(cls, degrees: float) -> float:
        """Convert degrees to radians."""
        return math.radians(degrees)
    
    @classmethod
    def haversine_distance(
        cls,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate great-circle distance between two GPS points.
        
        Uses the haversine formula:
        a = sin²(Δφ/2) + cos φ1 ⋅ cos φ2 ⋅ sin²(Δλ/2)
        c = 2 ⋅ atan2( √a, √(1−a) )
        d = R ⋅ c
        
        Args:
            lat1: Latitude of point 1 (degrees)
            lon1: Longitude of point 1 (degrees)
            lat2: Latitude of point 2 (degrees)
            lon2: Longitude of point 2 (degrees)
            
        Returns:
            Distance in kilometers
        """
        # Convert all coordinates to float (handle Decimal)
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
        
        # Convert to radians
        phi1 = cls._to_radians(lat1)
        phi2 = cls._to_radians(lat2)
        delta_phi = cls._to_radians(lat2 - lat1)
        delta_lambda = cls._to_radians(lon2 - lon1)
        
        # Haversine formula
        a = (
            math.sin(delta_phi / 2) ** 2 +
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return cls.EARTH_RADIUS_KM * c
    
    @classmethod
    def _get_active_stations(
        cls,
        state: Optional[str] = None,
        district: Optional[str] = None,
        city: Optional[str] = None
    ) -> QuerySet:
        """
        Get queryset of active police stations, optionally filtered.
        
        Args:
            state: Filter by state name (optional)
            district: Filter by district name (optional)
            city: Filter by city name (optional)
            
        Returns:
            QuerySet of active PoliceStation objects
        """
        qs = PoliceStation.objects.filter(is_active=True, is_deleted=False)
        
        if state:
            qs = qs.filter(state__iexact=state)
        if district:
            qs = qs.filter(district__iexact=district)
        if city:
            qs = qs.filter(city__iexact=city)
        
        return qs
    
    @classmethod
    def find_nearest_station(
        cls,
        latitude: float,
        longitude: float,
        state: Optional[str] = None,
        district: Optional[str] = None,
        city: Optional[str] = None,
        max_distance_km: Optional[float] = None
    ) -> Optional[PoliceStation]:
        """
        Find the nearest police station to given GPS coordinates.
        
        Args:
            latitude: Incident latitude (degrees, -90 to 90)
            longitude: Incident longitude (degrees, -180 to 180)
            state: Optional state filter (finds nearest within state)
            district: Optional district filter
            city: Optional city filter
            max_distance_km: Maximum distance to consider (default: 500km)
            
        Returns:
            Nearest PoliceStation or None if no station found within max distance
            
        Raises:
            ValueError: If coordinates are invalid
        """
        # Validate coordinates
        cls._validate_coordinates(latitude, longitude)
        
        max_distance = max_distance_km or cls.MAX_ROUTING_DISTANCE_KM
        
        stations = cls._get_active_stations(state, district, city)
        
        nearest_station = None
        nearest_distance = float('inf')
        
        for station in stations:
            distance = cls.haversine_distance(
                latitude, longitude,
                station.latitude, station.longitude
            )
            
            if distance < nearest_distance and distance <= max_distance:
                nearest_distance = distance
                nearest_station = station
        
        return nearest_station
    
    @classmethod
    def find_nearest_station_with_distance(
        cls,
        latitude: float,
        longitude: float,
        state: Optional[str] = None,
        district: Optional[str] = None,
        city: Optional[str] = None,
        max_distance_km: Optional[float] = None
    ) -> Tuple[Optional[PoliceStation], Optional[float]]:
        """
        Find nearest station and return both station and distance.
        
        Same as find_nearest_station but also returns the distance.
        
        Args:
            latitude: Incident latitude
            longitude: Incident longitude
            state: Optional state filter
            district: Optional district filter
            city: Optional city filter
            max_distance_km: Maximum distance to consider
            
        Returns:
            Tuple of (PoliceStation or None, distance in km or None)
        """
        cls._validate_coordinates(latitude, longitude)
        
        max_distance = max_distance_km or cls.MAX_ROUTING_DISTANCE_KM
        
        stations = cls._get_active_stations(state, district, city)
        
        nearest_station = None
        nearest_distance = float('inf')
        
        for station in stations:
            distance = cls.haversine_distance(
                latitude, longitude,
                station.latitude, station.longitude
            )
            
            if distance < nearest_distance and distance <= max_distance:
                nearest_distance = distance
                nearest_station = station
        
        if nearest_station is None:
            return None, None
        
        return nearest_station, round(nearest_distance, 2)
    
    @classmethod
    def find_stations_within_radius(
        cls,
        latitude: float,
        longitude: float,
        radius_km: float,
        state: Optional[str] = None,
        limit: Optional[int] = None
    ) -> list:
        """
        Find all stations within a given radius, sorted by distance.
        
        Useful for showing nearby stations or fallback routing.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius_km: Search radius in kilometers
            state: Optional state filter
            limit: Maximum number of stations to return
            
        Returns:
            List of tuples (PoliceStation, distance_km) sorted by distance
        """
        cls._validate_coordinates(latitude, longitude)
        
        if radius_km <= 0:
            raise ValueError("Radius must be positive")
        
        stations = cls._get_active_stations(state=state)
        
        results = []
        for station in stations:
            distance = cls.haversine_distance(
                latitude, longitude,
                station.latitude, station.longitude
            )
            
            if distance <= radius_km:
                results.append((station, round(distance, 2)))
        
        # Sort by distance
        results.sort(key=lambda x: x[1])
        
        if limit:
            results = results[:limit]
        
        return results
    
    @classmethod
    def calculate_distance_to_station(
        cls,
        latitude: float,
        longitude: float,
        station: PoliceStation
    ) -> float:
        """
        Calculate distance from a point to a specific station.
        
        Args:
            latitude: Point latitude
            longitude: Point longitude
            station: PoliceStation object
            
        Returns:
            Distance in kilometers
        """
        cls._validate_coordinates(latitude, longitude)
        
        return round(
            cls.haversine_distance(
                latitude, longitude,
                station.latitude, station.longitude
            ),
            2
        )
    
    @classmethod
    def _validate_coordinates(cls, latitude: float, longitude: float) -> None:
        """
        Validate GPS coordinates are within valid range.
        
        Args:
            latitude: Latitude to validate (-90 to 90)
            longitude: Longitude to validate (-180 to 180)
            
        Raises:
            ValueError: If coordinates are out of range
        """
        lat = float(latitude)
        lon = float(longitude)
        
        if not -90 <= lat <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
        
        if not -180 <= lon <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {lon}")
