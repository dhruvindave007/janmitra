"""
JurisdictionService: Police station routing.

Routing priority:
1. Area-name match (exact locality → predefined station mapping)
2. GPS haversine distance (fallback)

Usage:
    from reports.services import JurisdictionService
    
    # Find station by area name + GPS (preferred)
    station = JurisdictionService.find_nearest_station(
        lat, lon, area_name="Navrangpura", city="Ahmedabad"
    )
    
    # Find nearest station by GPS only
    station = JurisdictionService.find_nearest_station(lat, lon)
"""

import logging
import math
from decimal import Decimal
from typing import Optional, Tuple

from django.db.models import QuerySet

from core.models import PoliceStation

logger = logging.getLogger('janmitra.jurisdiction')


class JurisdictionService:
    """
    Service for police station routing.
    
    Priority:
    1. Area-name match via AhmedabadZoneService (for known Ahmedabad areas)
    2. Haversine GPS distance (universal fallback)
    
    All distances are in kilometers.
    """
    
    EARTH_RADIUS_KM = 6371.0
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
        
        Returns: Distance in kilometers
        """
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        
        phi1 = cls._to_radians(lat1)
        phi2 = cls._to_radians(lat2)
        delta_phi = cls._to_radians(lat2 - lat1)
        delta_lambda = cls._to_radians(lon2 - lon1)
        
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
        """Get queryset of active police stations, optionally filtered."""
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
        max_distance_km: Optional[float] = None,
        area_name: Optional[str] = None,
        sub_locality: Optional[str] = None,
    ) -> Optional[PoliceStation]:
        """
        Find the nearest police station to given GPS coordinates.
        
        Routing priority:
        1. Area-name match (if area_name/sub_locality provided)
        2. GPS haversine distance
        
        Args:
            latitude: Incident latitude (degrees, -90 to 90)
            longitude: Incident longitude (degrees, -180 to 180)
            state: Optional state filter
            district: Optional district filter
            city: Optional city filter
            max_distance_km: Maximum distance to consider (default: 500km)
            area_name: Area/locality name for area-based routing
            sub_locality: Sub-locality name for area-based routing
            
        Returns:
            Nearest PoliceStation or None
        """
        cls._validate_coordinates(latitude, longitude)
        
        # Priority 1: Area-name based routing
        if area_name or sub_locality:
            try:
                from reports.services.ahmedabad_zones import AhmedabadZoneService
                
                station = AhmedabadZoneService.find_station_by_area(
                    area_name=area_name,
                    sub_locality=sub_locality,
                    city=city,
                )
                if station:
                    logger.info(
                        f"Station routed by area: {station.name} "
                        f"(area='{area_name}', sub='{sub_locality}')"
                    )
                    return station
            except Exception as e:
                logger.warning(f"Area-based routing failed: {e}")
        
        # Priority 2: GPS haversine distance
        max_distance = max_distance_km or cls.MAX_ROUTING_DISTANCE_KM
        
        # If within Ahmedabad bounds, prefer Ahmedabad stations
        try:
            from reports.services.ahmedabad_zones import AhmedabadZoneService
            if AhmedabadZoneService.is_within_ahmedabad(latitude, longitude):
                ahm_stations = cls._get_active_stations(
                    state='Gujarat', city='Ahmedabad'
                )
                station = cls._find_nearest_in_queryset(
                    latitude, longitude, ahm_stations, max_distance
                )
                if station:
                    logger.info(
                        f"Station routed by GPS (Ahmedabad): {station.name} "
                        f"({latitude}, {longitude})"
                    )
                    return station
        except Exception:
            pass
        
        # General fallback: search all stations
        stations = cls._get_active_stations(state, district, city)
        station = cls._find_nearest_in_queryset(
            latitude, longitude, stations, max_distance
        )
        if station:
            logger.info(
                f"Station routed by GPS (general): {station.name} "
                f"({latitude}, {longitude})"
            )
        return station
    
    @classmethod
    def _find_nearest_in_queryset(
        cls,
        latitude: float,
        longitude: float,
        stations: QuerySet,
        max_distance: float,
    ) -> Optional[PoliceStation]:
        """Find the nearest station in a queryset."""
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
        max_distance_km: Optional[float] = None,
        area_name: Optional[str] = None,
        sub_locality: Optional[str] = None,
    ) -> Tuple[Optional[PoliceStation], Optional[float]]:
        """
        Find nearest station and return both station and distance.
        
        Returns:
            Tuple of (PoliceStation or None, distance in km or None)
        """
        cls._validate_coordinates(latitude, longitude)
        
        station = cls.find_nearest_station(
            latitude, longitude,
            state=state, district=district, city=city,
            max_distance_km=max_distance_km,
            area_name=area_name, sub_locality=sub_locality,
        )
        
        if station is None:
            return None, None
        
        distance = round(cls.haversine_distance(
            latitude, longitude,
            station.latitude, station.longitude
        ), 2)
        
        return station, distance
    
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
        """Calculate distance from a point to a specific station."""
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
        """Validate GPS coordinates are within valid range."""
        lat = float(latitude)
        lon = float(longitude)
        
        if not -90 <= lat <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
        
        if not -180 <= lon <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {lon}")
