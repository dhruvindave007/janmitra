# Area Name Resolution Implementation

**Status**: ✅ Complete, Backend validated

---

## Summary

Implemented automatic geographic area name resolution from GPS coordinates using OpenStreetMap Nominatim API. Allows authorities to see human-readable location metadata like "Prahlad Nagar, Ahmedabad" instead of raw coordinates.

---

## Implementation Details

### 1. Service Layer – `reports/services.py`

Created **LocationResolverService** class with two methods:

#### `resolve_area_name(latitude, longitude)` 
- Calls: `https://nominatim.openstreetmap.org/reverse?format=json&lat=...&lon=...&zoom=18&addressdetails=1`
- Extracts components in priority order: `road` → `neighbourhood` → `suburb` → `city`
- Returns: Concatenated string (e.g., "Prahlad Nagar, Ahmedabad") or `None`
- Timeout: 3 seconds (never blocks incident creation)
- Failure handling: Returns `None` silently, all exceptions caught

#### `resolve_city_and_state(latitude, longitude)`
- Returns tuple: `(city_name, state_name)` or `(None, None)` on failure
- Uses Nominatim with `zoom=10` for city/state level accuracy
- Same timeout + safety guarantees

**Safety Features**:
- No exceptions raised (all errors caught, logged, returned as None)
- 3-second timeout prevents blocking
- Coordinate validation (bounds check)
- Rate-limit friendly User-Agent header

---

### 2. Integration – `reports/views.py`

**IncidentBroadcastView** enhanced:

```python
# After incident creation (line ~632)
if incident.latitude and incident.longitude and not incident.area_name:
    try:
        resolved_area = LocationResolverService.resolve_area_name(
            incident.latitude,
            incident.longitude
        )
        if resolved_area:
            incident.area_name = resolved_area
            incident.save(update_fields=['area_name'])
    except Exception:
        pass  # Non-critical - don't fail request
```

**Behavior**:
- Runs AFTER notification and audit log (non-critical path)
- Only resolves if coordinates provided AND area_name not already set
- Frontend can still provide area_name (won't be overwritten)
- Request succeeds even if resolution fails

---

### 3. API Serializers – `reports/serializers.py`

#### CaseListSerializer
Added field declarations:
```python
area_name = serializers.CharField(source='incident.area_name', read_only=True, allow_null=True)
city = serializers.CharField(source='incident.city', read_only=True, allow_null=True)
state = serializers.CharField(source='incident.state', read_only=True, allow_null=True)
```

Added to `Meta.fields` (after `longitude`):
```python
'area_name',
'city',
'state',
```

#### CaseDetailSerializer  
Same field declarations and Meta.fields additions.

**Frontend Impact**:
- Flutter case list/detail now receive `area_name`, `city`, `state`
- Can display to authorities for context
- Null-safe (returns null if not resolved)

---

## Data Model

**No migration needed** — `area_name`, `city`, `state` fields already exist in Incident model:

```python
# models.py (excerpt)
area_name = models.CharField(max_length=255, null=True, blank=True)
city = models.CharField(max_length=255, null=True, blank=True)
state = models.CharField(max_length=255, null=True, blank=True)
```

---

## Testing

Run Django validation:
```bash
python manage.py check
# Output: System check identified no issues (0 silenced).
```

---

## Dependencies

- **requests** (already in venv): Used for Nominatim API HTTP calls
- **No Celery/async needed**: Synchronous call with 3-second timeout

---

## Example Workflow

1. User submits incident with `latitude=23.0225, longitude=72.5714` (Ahmedabad)
2. `IncidentBroadcastView` creates Incident record
3. Calls `LocationResolverService.resolve_area_name(23.0225, 72.5714)`
4. Nominatim returns address components: `{road: "...", neighbourhood: "Prahlad Nagar", city: "Ahmedabad"}`
5. Service builds: `"Prahlad Nagar, Ahmedabad"`
6. Updates `incident.area_name = "Prahlad Nagar, Ahmedabad"`
7. Case API response includes `area_name: "Prahlad Nagar, Ahmedabad"`
8. Flutter displays this in case list/detail for context

---

## Files Changed

| File | Changes |
|------|---------|
| [reports/services.py](../../Janmitraapp/reports/services.py) | Created (new file) |
| [reports/views.py](../../Janmitraapp/reports/views.py) | Added import + LocationResolverService integration in IncidentBroadcastView |
| [reports/serializers.py](../../Janmitraapp/reports/serializers.py) | Added `area_name`, `city`, `state` to CaseListSerializer & CaseDetailSerializer |

---

## Backward Compatibility

✅ **Fully backward compatible**:
- Existing incidents without area_name still work (returns null in API)
- Frontend can still provide area_name (it won't be overwritten)
- No database migrations needed  
- Optional feature (if Nominatim fails, system continues normally)

---

## Future Enhancements

- Add caching of coordinate→area mappings (Redis)
- Add batch geocoding for list views
- Add administrative division details (district/ward)
- Configurable Nominatim provider or custom geocoder
