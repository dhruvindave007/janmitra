"""
BroadcastIncidentService: Handles incident creation workflow.

V2 Strict Location Enforcement:
- incident_location (manual text) is REQUIRED, validated for precision
- GPS (latitude/longitude) is MANDATORY for audit/logging only
- GPS is NOT used for routing; JANMITRA users route to assigned station
- Category is REQUIRED and must be one of 18 predefined values

Citizen submits incident → System creates case with:
- status = NEW
- current_level = L1
- sla_deadline = current time + 48 hours
- Police station from user assignment (JANMITRA) or GPS (others)
- System message added for case creation
- L1 and L2 at police station notified

Usage:
    from reports.services.broadcast import BroadcastIncidentService
    
    incident, case, media_count, errors = BroadcastIncidentService.execute(
        user=citizen_user,
        text_content="Description of incident",
        incident_location="SG Highway near Iscon Mall",
        category="THEFT",
        latitude=12.9716,
        longitude=77.5946,
        media_files=[file1, file2],
    )
"""

import logging
import os
import re
from datetime import timedelta
from typing import Optional, List, Tuple
from decimal import Decimal

from django.utils import timezone
from django.db import transaction

from authentication.models import UserRole
from reports.models import (
    Incident, Case, IncidentMedia, IncidentMediaType,
    CaseLevel, CaseStatus, CaseStatusHistory, IncidentCategory
)
from reports.services.jurisdiction import JurisdictionService
from reports.services.investigation import InvestigationService
from notifications.services import NotificationService

logger = logging.getLogger('janmitra.broadcast')

# Vague location terms that should be rejected
VAGUE_LOCATION_TERMS = [
    'road', 'area', 'nearby', 'somewhere', 'here', 'there',
    'unknown', 'na', 'n/a', 'none', 'nil', 'xyz', 'abc',
    'test', 'asdf', 'location',
]


class IncidentCreationError(Exception):
    """Raised when incident creation fails."""
    pass


class BroadcastIncidentService:
    """
    Service for creating incidents and cases.
    
    V2 Flow:
    1. Validate inputs (strict location + GPS + category)
    2. Determine police station:
       - JANMITRA → use user.police_station (assigned by admin)
       - Others → GPS-based JurisdictionService routing
    3. Create incident (immutable record)
    4. Create case with status=NEW, current_level=L1, sla_deadline=now+48h
    5. Attach media if provided (with validation)
    6. Add system message indicating case creation
    7. Notify L1 and L2 users of that police station only
    """
    
    MIN_LOCATION_LENGTH = 5
    
    @classmethod
    def _validate_incident_location(cls, location: str) -> str:
        """Validate incident_location for precision and reject vague values."""
        if not location or not location.strip():
            raise IncidentCreationError("Please enter a valid incident location")
        
        location = location.strip()
        
        if len(location) < cls.MIN_LOCATION_LENGTH:
            raise IncidentCreationError(
                "Please enter a valid incident location"
            )
        
        # Reject vague single-word locations
        location_lower = location.lower().strip()
        if location_lower in VAGUE_LOCATION_TERMS:
            raise IncidentCreationError(
                "Please enter a precise location (e.g., Street / Landmark / Area)"
            )
        
        # Reject if ALL words are vague
        words = re.split(r'\s+', location_lower)
        if all(w in VAGUE_LOCATION_TERMS for w in words if len(w) > 1):
            raise IncidentCreationError(
                "Please enter a precise location (e.g., Street / Landmark / Area)"
            )
        
        return location
    
    @classmethod
    def execute(
        cls,
        user,
        text_content: str,
        incident_location: str,
        category: str,
        latitude: float,
        longitude: float,
        media_files: Optional[List] = None,
        area_name: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Tuple[Incident, Case, int, List[str]]:
        """
        Create an incident and associated case.
        
        Args:
            user: Citizen user submitting the incident
            text_content: Description of the incident (required)
            incident_location: Manual location text (required, validated)
            category: Incident category (required, from predefined list)
            latitude: GPS latitude (required for audit)
            longitude: GPS longitude (required for audit)
            media_files: List of uploaded files (optional, max 3)
            area_name: Resolved area name from geocoding (optional)
            city: City name (optional)
            state: State name (optional)
            
        Returns:
            Tuple of (Incident, Case, media_uploaded_count, media_errors)
            
        Raises:
            IncidentCreationError: If critical validation fails
        """
        # Validate required description
        if not text_content or not text_content.strip():
            raise IncidentCreationError("Incident description is required")
        text_content = text_content.strip()
        
        # Validate incident_location (strict)
        incident_location = cls._validate_incident_location(incident_location)
        
        # Validate category (required, must be from predefined list)
        if not category or category not in IncidentCategory.VALID_VALUES:
            raise IncidentCreationError(
                "Please select a valid incident category"
            )
        
        # Validate GPS (mandatory for audit)
        if latitude is None or longitude is None:
            raise IncidentCreationError("GPS location is required")
        
        # Sanitize inputs
        if area_name and len(area_name) > 255:
            area_name = area_name[:255]
        if city and len(city) > 255:
            city = city[:255]
        if state and len(state) > 255:
            state = state[:255]
        
        # Validate and convert coordinates
        try:
            lat_decimal = Decimal(str(latitude))
            lon_decimal = Decimal(str(longitude))
            if not (-90 <= float(lat_decimal) <= 90):
                raise IncidentCreationError("Invalid latitude value")
            if not (-180 <= float(lon_decimal) <= 180):
                raise IncidentCreationError("Invalid longitude value")
        except (ValueError, TypeError):
            raise IncidentCreationError("Invalid GPS coordinates")
        
        # Determine police station (GPS NOT used for routing)
        station = None
        if user.role == UserRole.JANMITRA:
            station = user.police_station
            if station is None:
                raise IncidentCreationError(
                    "You are not assigned to a police station. "
                    "Please contact administration."
                )
            logger.info(
                "V2 routing: JANMITRA user=%s → station=%s",
                user.identifier, station.name
            )
        else:
            # Non-JANMITRA: still use GPS for station routing
            try:
                station = JurisdictionService.find_nearest_station(
                    float(lat_decimal), float(lon_decimal)
                )
            except Exception:
                pass
        
        # Calculate SLA deadline: current time + 48 hours
        sla_deadline = timezone.now() + timedelta(hours=48)
        
        # Use atomic transaction for data consistency
        with transaction.atomic():
            # Create incident (immutable record)
            incident = Incident.objects.create(
                submitted_by=user,
                text_content=text_content,
                incident_location=incident_location,
                category=category,
                latitude=lat_decimal,
                longitude=lon_decimal,
                area_name=area_name,
                city=city,
                state=state,
            )
            
            # Create case with required initial state
            case = Case.objects.create(
                incident=incident,
                police_station=station,
                current_level=CaseLevel.L1,
                status=CaseStatus.NEW,
                sla_deadline=sla_deadline,
            )
            
            # Record status history
            CaseStatusHistory.objects.create(
                case=case,
                from_status=None,
                to_status=CaseStatus.NEW,
                from_level=None,
                to_level=CaseLevel.L1,
                changed_by=None,
                reason="Case created from citizen incident submission",
                is_auto_escalation=False,
            )
            
            # Handle media files (inside transaction for consistency)
            media_uploaded = 0
            media_errors = []
            if media_files:
                media_uploaded, media_errors = cls._process_media_files(
                    incident=incident,
                    user=user,
                    media_files=media_files
                )
            
            # Add system message for case creation
            station_info = f" Assigned to: {station.name}" if station else ""
            InvestigationService.send_system_message(
                case=case,
                text=f"Case created from incident submission.{station_info} SLA deadline: {sla_deadline.strftime('%Y-%m-%d %H:%M')} UTC."
            )
        
        # Notify L1 and L2 at the police station (outside transaction)
        try:
            NotificationService.notify_new_case_l1_l2(case)
        except Exception:
            pass
        
        return incident, case, media_uploaded, media_errors
    
    @classmethod
    def _process_media_files(
        cls,
        incident: Incident,
        user,
        media_files: List
    ) -> Tuple[int, List[str]]:
        """
        Process and validate media file uploads.
        
        Args:
            incident: The incident to attach media to
            user: The user uploading the files
            media_files: List of uploaded files
            
        Returns:
            Tuple of (uploaded_count, error_messages)
        """
        media_uploaded = 0
        media_errors = []
        
        # Limit to maximum allowed files
        files_to_process = media_files[:IncidentMediaType.MAX_FILES_PER_INCIDENT]
        
        for uploaded_file in files_to_process:
            try:
                # Validate file
                error = cls._validate_media_file(uploaded_file)
                if error:
                    media_errors.append(error)
                    continue
                
                # Determine media type from extension
                ext = os.path.splitext(uploaded_file.name)[1].lower()
                media_type = cls._get_media_type(ext)
                
                if media_type is None:
                    media_errors.append(f"Unsupported file type: {uploaded_file.name}")
                    continue
                
                # Check file size against type-specific limit
                max_size = IncidentMediaType.MAX_SIZES.get(media_type, 10 * 1024 * 1024)
                if uploaded_file.size > max_size:
                    max_mb = max_size / (1024 * 1024)
                    media_errors.append(f"File too large ({max_mb}MB max): {uploaded_file.name}")
                    continue
                
                # Create media record
                IncidentMedia.objects.create(
                    incident=incident,
                    file=uploaded_file,
                    media_type=media_type,
                    original_filename=uploaded_file.name[:255],
                    file_size=uploaded_file.size,
                    content_type=getattr(uploaded_file, 'content_type', ''),
                    uploaded_by=user,
                )
                media_uploaded += 1
                
            except Exception as e:
                media_errors.append(f"Error processing {uploaded_file.name}: {str(e)}")
        
        return media_uploaded, media_errors
    
    @classmethod
    def _validate_media_file(cls, uploaded_file) -> Optional[str]:
        """
        Validate an uploaded media file.
        
        Args:
            uploaded_file: The uploaded file object
            
        Returns:
            Error message string or None if valid
        """
        if not uploaded_file:
            return "Empty file"
        
        if not uploaded_file.name:
            return "File name is required"
        
        if uploaded_file.size <= 0:
            return "File is empty"
        
        # Check extension
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if not ext:
            return "File must have an extension"
        
        # Validate MIME type matches extension
        content_type = getattr(uploaded_file, 'content_type', '')
        media_type = cls._get_media_type(ext)
        
        if media_type is None:
            return f"Invalid file extension: {ext}"
        
        # Verify content type matches declared type
        allowed_mimes = IncidentMediaType.ALLOWED_MIME_TYPES.get(media_type, [])
        if content_type and content_type not in allowed_mimes:
            # Allow if no content type provided (some clients don't send it)
            if content_type != 'application/octet-stream':
                return f"Invalid content type for {media_type}: {content_type}"
        
        return None
    
    @classmethod
    def _get_media_type(cls, extension: str) -> Optional[str]:
        """
        Determine media type from file extension.
        
        Args:
            extension: File extension (e.g., '.jpg')
            
        Returns:
            Media type (photo/video) or None if unsupported
        """
        ext = extension.lower()
        
        for media_type, extensions in IncidentMediaType.ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                return media_type
        
        return None
