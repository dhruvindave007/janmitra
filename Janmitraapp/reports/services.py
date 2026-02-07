"""
Services for incident/case handling.

Includes:
- LocationResolverService: Reverse geocoding via OpenStreetMap Nominatim API
"""

import requests
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class LocationResolverService:
    """
    Resolves geographic area names from GPS coordinates using OpenStreetMap Nominatim.
    
    Nominatim API: https://nominatim.openstreetmap.org/reverse
    
    Safe by design:
    - 3-second timeout (never blocks incident creation)
    - Returns None on any failure
    - No exceptions raised
    """
    
    NOMINATIM_API = "https://nominatim.openstreetmap.org/reverse"
    TIMEOUT_SECONDS = 3
    ZOOM_LEVEL = 18  # Detailed address level
    
    @staticmethod
    def resolve_area_name(latitude, longitude):
        """
        Resolve area name from GPS coordinates.
        
        Args:
            latitude: Decimal latitude coordinate
            longitude: Decimal longitude coordinate
            
        Returns:
            str: Human-readable area name (e.g., "Prahlad Nagar, near Iscon Circle")
                 None if resolution fails or coordinates are invalid
                 
        Examples:
            >>> LocationResolverService.resolve_area_name(Decimal("23.0225"), Decimal("72.5714"))
            "Prahlad Nagar, Ahmedabad"
            
            >>> LocationResolverService.resolve_area_name(None, None)
            None
        """
        try:
            # Validate inputs
            if latitude is None or longitude is None:
                return None
            
            # Convert to float for API call
            lat = float(latitude)
            lon = float(longitude)
            
            # Bounds check (valid Earth coordinates)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                logger.warning(f"Invalid coordinates: lat={lat}, lon={lon}")
                return None
            
            # Build request
            params = {
                'format': 'json',
                'lat': lat,
                'lon': lon,
                'zoom': LocationResolverService.ZOOM_LEVEL,
                'addressdetails': 1,  # Include detailed address breakdown
            }
            
            logger.info(f"[LocationResolver] Resolving {lat}, {lon}")
            
            # Call Nominatim API with timeout
            response = requests.get(
                LocationResolverService.NOMINATIM_API,
                params=params,
                timeout=LocationResolverService.TIMEOUT_SECONDS,
                headers={
                    'User-Agent': 'JanMitra/1.0 (https://github.com/dhruvindave007/janmitra)',
                }
            )
            response.raise_for_status()  # Raise on 4xx/5xx
            
            data = response.json()
            address = data.get('address', {})
            
            # Build area name from address components in priority order
            area_parts = []
            
            # Priority: road -> neighbourhood -> suburb -> city
            for key in ['road', 'neighbourhood', 'suburb', 'city']:
                if key in address and address[key]:
                    area_parts.append(address[key])
            
            # If we got no useful address, try state/country as fallback
            if not area_parts:
                if 'state' in address and address['state']:
                    area_parts.append(address['state'])
                if 'country' in address and address['country']:
                    area_parts.append(address['country'])
            
            # Build readable string
            if area_parts:
                area_name = ', '.join(area_parts[:3])  # Limit to 3 components for readability
                logger.info(f"[LocationResolver] Resolved: {area_name}")
                return area_name
            
            logger.warning(f"[LocationResolver] No address found for {lat}, {lon}")
            return None
            
        except requests.Timeout:
            logger.warning(f"[LocationResolver] Nominatim API timeout for {latitude}, {longitude}")
            return None
        except requests.ConnectionError:
            logger.warning(f"[LocationResolver] Nominatim API connection error")
            return None
        except requests.HTTPError as e:
            logger.warning(f"[LocationResolver] Nominatim API error: {e}")
            return None
        except ValueError as e:
            logger.warning(f"[LocationResolver] Invalid coordinates: {latitude}, {longitude} - {e}")
            return None
        except Exception as e:
            logger.error(f"[LocationResolver] Unexpected error: {e}", exc_info=True)
            return None
    
    @staticmethod
    def resolve_city_and_state(latitude, longitude):
        """
        Resolve city and state from GPS coordinates.
        
        Returns:
            tuple: (city_name, state_name) or (None, None) if resolution fails
        """
        try:
            if latitude is None or longitude is None:
                return None, None
            
            lat = float(latitude)
            lon = float(longitude)
            
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None, None
            
            params = {
                'format': 'json',
                'lat': lat,
                'lon': lon,
                'zoom': 10,  # City/state level
                'addressdetails': 1,
            }
            
            response = requests.get(
                LocationResolverService.NOMINATIM_API,
                params=params,
                timeout=LocationResolverService.TIMEOUT_SECONDS,
                headers={
                    'User-Agent': 'JanMitra/1.0',
                }
            )
            response.raise_for_status()
            
            data = response.json()
            address = data.get('address', {})
            
            city = address.get('city') or address.get('town') or address.get('village')
            state = address.get('state')
            
            return city, state
            
        except Exception as e:
            logger.warning(f"[LocationResolver] Error resolving city/state: {e}")
            return None, None
