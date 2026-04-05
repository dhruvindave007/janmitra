"""
Ahmedabad Police Zone & Area Mapping Service.

Maps Ahmedabad city areas/localities to their correct police stations
based on the real Ahmedabad City Police zone structure.

Ahmedabad Police operates under the Commissioner of Police with
the city divided into 7 operational zones containing ~35 police stations.

Routing priority:
1. Area-name match (exact or fuzzy against jurisdiction_areas)
2. GPS haversine distance (fallback)

Usage:
    from reports.services.ahmedabad_zones import AhmedabadZoneService

    # Find station by area name
    station = AhmedabadZoneService.find_station_by_area("Navrangpura")

    # Check if coordinates are within Ahmedabad
    is_ahm = AhmedabadZoneService.is_within_ahmedabad(23.03, 72.57)
"""

import logging
from typing import Dict, List, Optional, Tuple

from core.models import PoliceStation

logger = logging.getLogger('janmitra.jurisdiction')

# Ahmedabad city bounding box (approximate)
AHMEDABAD_BOUNDS = {
    'lat_min': 22.920,
    'lat_max': 23.135,
    'lon_min': 72.450,
    'lon_max': 72.680,
}

# =============================================================================
# AHMEDABAD POLICE STATIONS — REAL DATA
# =============================================================================
# Each station entry:
#   code, name, lat, lon, zone, zone_name, areas[], address, phone
#
# Coordinates are for the station building or nearest known landmark.
# Areas list contains all localities/neighborhoods under jurisdiction.
# =============================================================================

AHMEDABAD_STATIONS: List[Dict] = [
    # =========================================================================
    # ZONE 1 — EAST ZONE (Old City East)
    # =========================================================================
    {
        'code': 'PS-GJ-AHM-001',
        'name': 'Shahibaug Police Station',
        'latitude': 23.0575,
        'longitude': 72.5870,
        'zone': 'Zone-1 East',
        'areas': [
            'Shahibaug', 'Shahibag', 'Gujarat University', 'RTO Circle',
            'Rajasthan Hospital', 'Lal Bungalow', 'Civil Hospital',
            'Asarwa', 'Dudheshwar',
        ],
        'address': 'Shahibaug Road, Shahibaug, Ahmedabad 380004',
        'phone': '079-25620242',
    },
    {
        'code': 'PS-GJ-AHM-002',
        'name': 'Dariapur Police Station',
        'latitude': 23.0285,
        'longitude': 72.5830,
        'zone': 'Zone-1 East',
        'areas': [
            'Dariapur', 'Teen Darwaza', 'Khamasa', 'Mirzapur',
            'Shahpur', 'Gheekanta', 'Kazipur',
        ],
        'address': 'Dariapur Road, Dariapur, Ahmedabad 380001',
        'phone': '079-25623800',
    },
    {
        'code': 'PS-GJ-AHM-003',
        'name': 'Kalupur Police Station',
        'latitude': 23.0315,
        'longitude': 72.5965,
        'zone': 'Zone-1 East',
        'areas': [
            'Kalupur', 'Kalupur Railway Station', 'Sarangpur',
            'Raipur', 'Kankaria North', 'Dudheshwar Road',
            'Raikhad', 'Khadia',
        ],
        'address': 'Near Kalupur Railway Station, Ahmedabad 380002',
        'phone': '079-25621777',
    },
    {
        'code': 'PS-GJ-AHM-004',
        'name': 'Gaekwad Haveli Police Station',
        'latitude': 23.0230,
        'longitude': 72.5855,
        'zone': 'Zone-1 East',
        'areas': [
            'Gaekwad Haveli', 'Bhadra', 'Manek Chowk', 'Lal Darwaza',
            'Dhalgarwad', 'Ratan Pole', 'Fernandez Bridge',
            'Gandhi Road', 'Bhadra Fort',
        ],
        'address': 'Near Bhadra Fort, Lal Darwaza, Ahmedabad 380001',
        'phone': '079-25506071',
    },
    {
        'code': 'PS-GJ-AHM-005',
        'name': 'Karanj Police Station',
        'latitude': 23.0195,
        'longitude': 72.5910,
        'zone': 'Zone-1 East',
        'areas': [
            'Karanj', 'Jamalpur', 'Khadia South', 'Raipur Darwaza',
            'Kalupur South', 'Khamasa South',
        ],
        'address': 'Karanj Road, Jamalpur, Ahmedabad 380001',
        'phone': '079-25621155',
    },

    # =========================================================================
    # ZONE 2 — WEST ZONE
    # =========================================================================
    {
        'code': 'PS-GJ-AHM-006',
        'name': 'Navrangpura Police Station',
        'latitude': 23.0365,
        'longitude': 72.5575,
        'zone': 'Zone-2 West',
        'areas': [
            'Navrangpura', 'CG Road', 'Panchwati', 'Law Garden',
            'Mithakhali', 'Stadium Circle', 'Municipal Market',
            'Swastik Cross Roads', 'Gujarat College',
        ],
        'address': 'Navrangpura, Near CG Road, Ahmedabad 380009',
        'phone': '079-26460396',
    },
    {
        'code': 'PS-GJ-AHM-007',
        'name': 'Vastrapur Police Station',
        'latitude': 23.0310,
        'longitude': 72.5285,
        'zone': 'Zone-2 West',
        'areas': [
            'Vastrapur', 'IIM Ahmedabad', 'IIM Road', 'University Road',
            'Gulbai Tekra', 'Vastrapur Lake', 'Helmet Circle',
            'Polytechnic', 'HL Commerce College',
        ],
        'address': 'Vastrapur, Near IIM Road, Ahmedabad 380015',
        'phone': '079-26301444',
    },
    {
        'code': 'PS-GJ-AHM-008',
        'name': 'Satellite Police Station',
        'latitude': 23.0135,
        'longitude': 72.5105,
        'zone': 'Zone-2 West',
        'areas': [
            'Satellite', 'Jodhpur', 'Prahlad Nagar', 'Drive-In Road',
            'Ambawadi', 'Jodhpur Cross Roads', 'Shyamal Cross Roads',
            'Jodhpur Gam', 'Anand Nagar Road', 'Satellite Road',
            'Judges Bungalow Road', 'Premchand Nagar',
        ],
        'address': 'Satellite Road, Near Jodhpur Cross Roads, Ahmedabad 380015',
        'phone': '079-26923388',
    },
    {
        'code': 'PS-GJ-AHM-009',
        'name': 'Bodakdev Police Station',
        'latitude': 23.0345,
        'longitude': 72.5015,
        'zone': 'Zone-2 West',
        'areas': [
            'Bodakdev', 'Thaltej', 'Judges Bungalow', 'SG Road East',
            'Thaltej Cross Roads', 'Bodakdev Lake',
            'Thaltej Tekra', 'Keshav Baug',
        ],
        'address': 'Bodakdev, Near Judges Bungalow Road, Ahmedabad 380054',
        'phone': '079-26858585',
    },
    {
        'code': 'PS-GJ-AHM-010',
        'name': 'Anandnagar Police Station',
        'latitude': 23.0300,
        'longitude': 72.5165,
        'zone': 'Zone-2 West',
        'areas': [
            'Anand Nagar', 'Prahladnagar', 'Ramdev Nagar', 'Sindhu Bhavan Road',
            'Anand Nagar Road', 'Prahladnagar Garden',
            'Corporate Road', 'Vejalpur Road',
        ],
        'address': 'Anand Nagar Road, Prahladnagar, Ahmedabad 380015',
        'phone': '079-26934934',
    },

    # =========================================================================
    # ZONE 3 — SOUTH ZONE
    # =========================================================================
    {
        'code': 'PS-GJ-AHM-011',
        'name': 'Maninagar Police Station',
        'latitude': 22.9960,
        'longitude': 72.5965,
        'zone': 'Zone-3 South',
        'areas': [
            'Maninagar', 'Kankaria', 'Khokhra', 'Maninagar East',
            'Kankaria Lake', 'Kankaria Zoo', 'Balvatika',
            'Kagdapith South', 'APMC',
        ],
        'address': 'Maninagar, Near Kankaria, Ahmedabad 380008',
        'phone': '079-25462602',
    },
    {
        'code': 'PS-GJ-AHM-012',
        'name': 'Isanpur Police Station',
        'latitude': 22.9775,
        'longitude': 72.6185,
        'zone': 'Zone-3 South',
        'areas': [
            'Isanpur', 'Isanpur Cross Roads', 'Hathijan',
            'Vinzol', 'Lambha', 'Vastral South',
        ],
        'address': 'Isanpur, Ahmedabad 382443',
        'phone': '079-25734110',
    },
    {
        'code': 'PS-GJ-AHM-013',
        'name': 'Vatva Police Station',
        'latitude': 22.9675,
        'longitude': 72.6355,
        'zone': 'Zone-3 South',
        'areas': [
            'Vatva', 'Vatva GIDC', 'Narol', 'Vatva Industrial Area',
            'Pirana', 'Gyaspur',
        ],
        'address': 'Vatva GIDC, Ahmedabad 382445',
        'phone': '079-25840091',
    },
    {
        'code': 'PS-GJ-AHM-014',
        'name': 'Danilimda Police Station',
        'latitude': 22.9965,
        'longitude': 72.5835,
        'zone': 'Zone-3 South',
        'areas': [
            'Danilimda', 'Gomtipur', 'Behrampura', 'Rakhial South',
            'Saraspur South', 'Shahwadi',
        ],
        'address': 'Danilimda, Ahmedabad 380028',
        'phone': '079-25622800',
    },
    {
        'code': 'PS-GJ-AHM-015',
        'name': 'Bapunagar Police Station',
        'latitude': 23.0190,
        'longitude': 72.6215,
        'zone': 'Zone-3 South',
        'areas': [
            'Bapunagar', 'CTM', 'Amraiwadi', 'Vastral', 'Ramol',
            'Nikol South', 'Odhav Road',
        ],
        'address': 'Bapunagar, CTM Cross Roads, Ahmedabad 380024',
        'phone': '079-22700202',
    },
    {
        'code': 'PS-GJ-AHM-016',
        'name': 'Odhav Police Station',
        'latitude': 22.9820,
        'longitude': 72.6585,
        'zone': 'Zone-3 South',
        'areas': [
            'Odhav', 'Odhav GIDC', 'Odhav Industrial Area',
            'Nikol East', 'Kathwada Road',
        ],
        'address': 'Odhav GIDC, Ahmedabad 382415',
        'phone': '079-22901155',
    },

    # =========================================================================
    # ZONE 4 — NORTH ZONE
    # =========================================================================
    {
        'code': 'PS-GJ-AHM-017',
        'name': 'Sabarmati Police Station',
        'latitude': 23.0855,
        'longitude': 72.5595,
        'zone': 'Zone-4 North',
        'areas': [
            'Sabarmati', 'Sabarmati Ashram', 'Usmanpura', 'Ashram Road North',
            'Subhash Bridge', 'Dudheshwar North', 'Motera South',
        ],
        'address': 'Sabarmati, Ahmedabad 380005',
        'phone': '079-27500800',
    },
    {
        'code': 'PS-GJ-AHM-018',
        'name': 'Chandkheda Police Station',
        'latitude': 23.1200,
        'longitude': 72.5685,
        'zone': 'Zone-4 North',
        'areas': [
            'Chandkheda', 'Zundal', 'New Ranip', 'Nana Chiloda',
            'Bhat', 'Tragad North', 'Jagatpur',
        ],
        'address': 'Chandkheda, Ahmedabad 382424',
        'phone': '079-29292100',
    },
    {
        'code': 'PS-GJ-AHM-019',
        'name': 'Sardarnagar Police Station',
        'latitude': 23.0785,
        'longitude': 72.5855,
        'zone': 'Zone-4 North',
        'areas': [
            'Sardarnagar', 'Saijpur', 'Saijpur Bogha', 'Kubernagar',
            'Thakkarnagar North', 'Wadaj North',
        ],
        'address': 'Sardarnagar, Ahmedabad 382475',
        'phone': '079-22680012',
    },
    {
        'code': 'PS-GJ-AHM-020',
        'name': 'Naroda Police Station',
        'latitude': 23.0895,
        'longitude': 72.6205,
        'zone': 'Zone-4 North',
        'areas': [
            'Naroda', 'Naroda Patiya', 'Naroda GIDC', 'Nikol',
            'Naroda Road', 'Vishala', 'Nikol Gam',
        ],
        'address': 'Naroda, Ahmedabad 382330',
        'phone': '079-22812003',
    },
    {
        'code': 'PS-GJ-AHM-021',
        'name': 'Ranip Police Station',
        'latitude': 23.0760,
        'longitude': 72.5475,
        'zone': 'Zone-4 North',
        'areas': [
            'Ranip', 'Old Ranip', 'Visat', 'Tragad', 'Sola Bhagwat',
            'New CG Road North', 'Ranip Gam',
        ],
        'address': 'Ranip, Near Visat Circle, Ahmedabad 382480',
        'phone': '079-27522290',
    },
    {
        'code': 'PS-GJ-AHM-022',
        'name': 'Meghaninagar Police Station',
        'latitude': 23.0600,
        'longitude': 72.5850,
        'zone': 'Zone-4 North',
        'areas': [
            'Meghaninagar', 'Thakkarnagar', 'Saijpur Bogha South',
            'Amraiwadi North', 'Krishnanagar', 'Rakhial North',
        ],
        'address': 'Meghaninagar, Ahmedabad 380016',
        'phone': '079-22685001',
    },

    # =========================================================================
    # ZONE 5 — CENTRAL ZONE
    # =========================================================================
    {
        'code': 'PS-GJ-AHM-023',
        'name': 'Ellis Bridge Police Station',
        'latitude': 23.0265,
        'longitude': 72.5645,
        'zone': 'Zone-5 Central',
        'areas': [
            'Ellis Bridge', 'Ashram Road', 'Paldi North', 'Income Tax',
            'Nehru Bridge', 'Riverfront', 'Lal Darwaza West',
            'Ellis Bridge Circle', 'Panchvati South',
        ],
        'address': 'Ellis Bridge, Ashram Road, Ahmedabad 380006',
        'phone': '079-26577100',
    },
    {
        'code': 'PS-GJ-AHM-024',
        'name': 'Naranpura Police Station',
        'latitude': 23.0520,
        'longitude': 72.5545,
        'zone': 'Zone-5 Central',
        'areas': [
            'Naranpura', 'Nirnaynagar', 'IOC Road', 'Naranpura Gam',
            'Bhudarpura', 'Ambawadi North', 'Pritamnagar',
            'Naranpura Cross Roads',
        ],
        'address': 'Naranpura, IOC Road, Ahmedabad 380013',
        'phone': '079-27431003',
    },
    {
        'code': 'PS-GJ-AHM-025',
        'name': 'Paldi Police Station',
        'latitude': 23.0130,
        'longitude': 72.5570,
        'zone': 'Zone-5 Central',
        'areas': [
            'Paldi', 'Vasna', 'Sardar Bridge', 'Vasna Barrage',
            'Paldi Cross Roads', 'Ellisbridge South',
            'Vasna Road', 'Mahalaxmi Cross Roads',
        ],
        'address': 'Paldi, Ahmedabad 380007',
        'phone': '079-26577010',
    },
    {
        'code': 'PS-GJ-AHM-026',
        'name': 'Kagdapith Police Station',
        'latitude': 23.0250,
        'longitude': 72.5770,
        'zone': 'Zone-5 Central',
        'areas': [
            'Kagdapith', 'Relief Road', 'Khanpur', 'Saraspur',
            'Kalupur West', 'Victoria Garden',
            'Riverfront East Bank', 'Khanpur Darwaza',
        ],
        'address': 'Kagdapith, Relief Road, Ahmedabad 380001',
        'phone': '079-25507777',
    },

    # =========================================================================
    # ZONE 6 — WEST OUTER / SG HIGHWAY
    # =========================================================================
    {
        'code': 'PS-GJ-AHM-027',
        'name': 'SG Highway Police Station',
        'latitude': 23.0385,
        'longitude': 72.5055,
        'zone': 'Zone-6 West Outer',
        'areas': [
            'SG Highway', 'Science City', 'Sola Road', 'Hebatpur',
            'Thaltej Road', 'Sola Overbridge', 'SG Road',
            'Science City Road', 'Hebatpur Road',
        ],
        'address': 'SG Highway, Near Science City, Ahmedabad 380060',
        'phone': '079-29294100',
    },
    {
        'code': 'PS-GJ-AHM-028',
        'name': 'Sola Police Station',
        'latitude': 23.0680,
        'longitude': 72.5155,
        'zone': 'Zone-6 West Outer',
        'areas': [
            'Sola', 'Sola Bridge', 'Ghatlodia', 'Thaltej North',
            'Sola Village', 'Sola Civil Hospital', 'Gota South',
            'Nirma University', 'Ghatlodia Circle',
        ],
        'address': 'Sola, Near Sola Bridge, Ahmedabad 380060',
        'phone': '079-27410103',
    },
    {
        'code': 'PS-GJ-AHM-029',
        'name': 'Gota Police Station',
        'latitude': 23.1090,
        'longitude': 72.5360,
        'zone': 'Zone-6 West Outer',
        'areas': [
            'Gota', 'Ognaj', 'Kali', 'Gota Cross Roads',
            'Vaishnodevi', 'Gota Gam', 'SP Ring Road North West',
        ],
        'address': 'Gota, Near Gota Cross Roads, Ahmedabad 382481',
        'phone': '079-29296100',
    },
    {
        'code': 'PS-GJ-AHM-030',
        'name': 'Bopal Police Station',
        'latitude': 23.0280,
        'longitude': 72.4710,
        'zone': 'Zone-6 West Outer',
        'areas': [
            'Bopal', 'South Bopal', 'Ghuma', 'Ambli', 'Shilaj',
            'Bopal Cross Roads', 'SP Ring Road South West',
            'Ambli Bopal Road',
        ],
        'address': 'Bopal, Ahmedabad 380058',
        'phone': '079-65432100',
    },
    {
        'code': 'PS-GJ-AHM-031',
        'name': 'Sarkhej Police Station',
        'latitude': 22.9810,
        'longitude': 72.4840,
        'zone': 'Zone-6 West Outer',
        'areas': [
            'Sarkhej', 'Juhapura', 'Sarkhej Roza', 'Sarkhej Gandhinagar Highway',
            'Makarba', 'Sanand Road',
        ],
        'address': 'Sarkhej, Ahmedabad 382210',
        'phone': '079-26892100',
    },

    # =========================================================================
    # ZONE 7 — SOUTH WEST
    # =========================================================================
    {
        'code': 'PS-GJ-AHM-032',
        'name': 'Vejalpur Police Station',
        'latitude': 23.0000,
        'longitude': 72.5300,
        'zone': 'Zone-7 South West',
        'areas': [
            'Vejalpur', 'Jivraj Park', 'Vejalpur Gam',
            'Anand Nagar South', 'Vasna South', 'Vejalpur Lake',
        ],
        'address': 'Vejalpur, Ahmedabad 380051',
        'phone': '079-26822100',
    },
    {
        'code': 'PS-GJ-AHM-033',
        'name': 'Madhupura Police Station',
        'latitude': 23.0400,
        'longitude': 72.6000,
        'zone': 'Zone-7 East Central',
        'areas': [
            'Madhupura', 'Rakhial', 'Gomtipur North', 'Chamanpura',
            'Madhupura Circle', 'Shahalam', 'Gomtipur',
        ],
        'address': 'Madhupura, Ahmedabad 380004',
        'phone': '079-22683900',
    },
    {
        'code': 'PS-GJ-AHM-034',
        'name': 'Wadaj Police Station',
        'latitude': 23.0650,
        'longitude': 72.5650,
        'zone': 'Zone-5 Central',
        'areas': [
            'Wadaj', 'IIM Road North', 'Sabarmati Riverfront North',
            'Wadaj Gam', 'Shantivan',
        ],
        'address': 'Wadaj, Ahmedabad 380013',
        'phone': '079-27550011',
    },
    {
        'code': 'PS-GJ-AHM-035',
        'name': 'Vastral Police Station',
        'latitude': 23.0050,
        'longitude': 72.6400,
        'zone': 'Zone-3 South',
        'areas': [
            'Vastral', 'Ramol', 'Vastral Gam', 'Vastral Lake',
            'Odhav West', 'SP Ring Road East',
        ],
        'address': 'Vastral, Ahmedabad 382418',
        'phone': '079-22901500',
    },
]


class AhmedabadZoneService:
    """
    Service for area-based police station routing in Ahmedabad.
    
    Provides accurate station lookup by area name, bypassing
    pure GPS distance for known Ahmedabad localities.
    """
    
    # Build area → station code index (lazy, built once)
    _area_index: Optional[Dict[str, str]] = None
    
    @classmethod
    def _build_area_index(cls) -> Dict[str, str]:
        """Build a lowercase area-name → station-code index."""
        if cls._area_index is not None:
            return cls._area_index
        
        index = {}
        for station_data in AHMEDABAD_STATIONS:
            code = station_data['code']
            for area in station_data['areas']:
                index[area.strip().lower()] = code
        
        cls._area_index = index
        return index
    
    @classmethod
    def is_within_ahmedabad(cls, latitude: float, longitude: float) -> bool:
        """Check if GPS coordinates fall within Ahmedabad city bounds."""
        return (
            AHMEDABAD_BOUNDS['lat_min'] <= float(latitude) <= AHMEDABAD_BOUNDS['lat_max'] and
            AHMEDABAD_BOUNDS['lon_min'] <= float(longitude) <= AHMEDABAD_BOUNDS['lon_max']
        )
    
    @classmethod
    def find_station_by_area(
        cls,
        area_name: Optional[str] = None,
        sub_locality: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Optional[PoliceStation]:
        """
        Find a police station by matching area/locality name.
        
        Tries multiple matching strategies:
        1. Exact match on area_name
        2. Exact match on sub_locality
        3. Substring match on area_name parts
        4. Match against station jurisdiction_areas in DB
        
        Args:
            area_name: Area/locality name (e.g., "Navrangpura, Ahmedabad")
            sub_locality: Sub-locality name (e.g., "Navrangpura")
            city: City name for verification
            
        Returns:
            PoliceStation or None
        """
        # Only route within Ahmedabad
        if city and city.lower() not in ('ahmedabad', 'amdavad', 'amadavad'):
            return None
        
        index = cls._build_area_index()
        
        # Strategy 1: Direct match on sub_locality (most specific)
        if sub_locality:
            code = index.get(sub_locality.strip().lower())
            if code:
                station = cls._get_station_by_code(code)
                if station:
                    logger.info(
                        f"Area-route: sub_locality='{sub_locality}' → {station.name}"
                    )
                    return station
        
        # Strategy 2: Direct match on area_name
        if area_name:
            normalized = area_name.strip().lower()
            code = index.get(normalized)
            if code:
                station = cls._get_station_by_code(code)
                if station:
                    logger.info(
                        f"Area-route: area_name='{area_name}' → {station.name}"
                    )
                    return station
        
        # Strategy 3: Split area_name by comma and try each part
        if area_name and ',' in area_name:
            parts = [p.strip().lower() for p in area_name.split(',')]
            for part in parts:
                code = index.get(part)
                if code:
                    station = cls._get_station_by_code(code)
                    if station:
                        logger.info(
                            f"Area-route: area_part='{part}' → {station.name}"
                        )
                        return station
        
        # Strategy 4: Substring match — check if any known area is IN the input
        search_text = ' '.join(filter(None, [
            area_name or '', sub_locality or '',
        ])).lower()
        
        if search_text:
            # Sort by longest area name first (more specific match wins)
            sorted_areas = sorted(index.keys(), key=len, reverse=True)
            for known_area in sorted_areas:
                if len(known_area) >= 4 and known_area in search_text:
                    code = index[known_area]
                    station = cls._get_station_by_code(code)
                    if station:
                        logger.info(
                            f"Area-route: substring='{known_area}' in '{search_text}' → {station.name}"
                        )
                        return station
        
        # Strategy 5: Check DB jurisdiction_areas field
        if area_name or sub_locality:
            search_term = sub_locality or area_name
            stations = PoliceStation.objects.filter(
                is_active=True,
                is_deleted=False,
                city__iexact='Ahmedabad',
                jurisdiction_areas__icontains=search_term,
            )
            if stations.exists():
                station = stations.first()
                logger.info(
                    f"Area-route: DB jurisdiction match '{search_term}' → {station.name}"
                )
                return station
        
        logger.debug(
            f"Area-route: no match for area='{area_name}', "
            f"sub_locality='{sub_locality}'"
        )
        return None
    
    @classmethod
    def _get_station_by_code(cls, code: str) -> Optional[PoliceStation]:
        """Fetch active station by code."""
        try:
            return PoliceStation.objects.get(
                code=code, is_active=True, is_deleted=False
            )
        except PoliceStation.DoesNotExist:
            return None
    
    @classmethod
    def get_zone_stations(cls, zone: str) -> list:
        """Get all stations in a specific zone."""
        return list(
            PoliceStation.objects.filter(
                zone__iexact=zone, is_active=True, is_deleted=False
            )
        )
    
    @classmethod
    def get_all_zones(cls) -> List[str]:
        """Get list of all unique zones."""
        return list(
            PoliceStation.objects.filter(
                is_active=True, is_deleted=False
            ).values_list('zone', flat=True).distinct().order_by('zone')
        )
    
    @classmethod
    def get_station_data(cls) -> List[Dict]:
        """Return the predefined station dataset for seeding."""
        return AHMEDABAD_STATIONS
    
    @classmethod
    def invalidate_cache(cls):
        """Clear the area index cache (call after DB changes)."""
        cls._area_index = None
