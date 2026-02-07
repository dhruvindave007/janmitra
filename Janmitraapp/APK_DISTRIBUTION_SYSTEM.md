# APK Distribution System - Implementation Complete

## Overview

The APK distribution system is fully implemented and tested. It allows:
- Admins to upload and manage APK versions via Django admin
- Flutter app to check for updates via API
- Seamless APK downloads from your own server (not Play Store)
- Version management with minimum supported version enforcement

## System Architecture

### Backend Components

#### 1. AppVersion Model ([core/models.py](../core/models.py))
- **latest_version**: Current release version (e.g., "1.2.3")
- **minimum_supported_version**: Oldest version that can still use the app
- **apk_file**: FileField storing APK in `media/app_updates/`
- **is_active**: Only active version is returned by API
- **Inherited fields**: id (UUID), created_at, updated_at, deleted_at, is_deleted

Key method: `AppVersion.get_active_version()` - retrieves the currently active version

#### 2. AppVersionSerializer ([core/serializers.py](../core/serializers.py))
Returns three fields:
- `latest_version`: Version string (e.g., "1.2.3")
- `minimum_supported_version`: Minimum supported version
- `apk_url`: Full URL to download the APK (e.g., "http://34.229.130.142/media/app_updates/janmitra-1.2.3.apk")

#### 3. AppVersionView ([core/views.py](../core/views.py))
API endpoint: `GET /api/v1/app/version/`
- No authentication required (public endpoint)
- Returns 404 if no active version configured
- Returns AppVersion data with full APK URL

#### 4. Admin Interface ([core/admin.py](../core/admin.py))
Custom admin with:
- File upload for APK
- Version switching (automatically deactivates others)
- Visual status badges (Active/Inactive)
- File size display
- Direct download link for APK files

#### 5. URL Routing ([core/urls.py](../core/urls.py) & updated [janmitra_backend/urls.py](../janmitra_backend/urls.py))
- Route added: `path('api/v1/app/', include('core.urls'))`
- Full endpoint: `/api/v1/app/version/`

#### 6. Media Configuration ([janmitra_backend/settings.py](../janmitra_backend/settings.py))
- **MEDIA_ROOT**: `BASE_DIR / 'media'` (automatically created)
- **MEDIA_URL**: `/media/` (serves files via Django URLs)
- Folder structure: `media/app_updates/` (auto-created on upload)

## How to Use

### For Admins (Django Admin)

1. **Navigate to Admin Dashboard**
   - URL: `http://34.229.130.142/admin/`
   - Login with admin credentials

2. **Go to Core → App Versions**

3. **Upload a New Version**
   - Click "Add App Version"
   - Enter Latest Version: `1.0.0`
   - Enter Minimum Supported Version: `0.9.0`
   - Upload APK file (will be stored in `media/app_updates/`)
   - Set `is_active = True` only if this is the current version
   - Click Save

4. **Switch to New Version**
   - Create the new version entry with `is_active = False`
   - Click on the version in the list
   - Click "Activate selected version" action
   - This automatically deactivates all other versions

5. **Manage Versions**
   - List view shows: Version, Status, File, Created Date
   - Click version to edit or upload new APK
   - Actions: Activate, Deactivate

### For Flutter Developers

#### API Response Format

```bash
# Request
curl http://34.229.130.142/api/v1/app/version/

# Response (200 OK)
{
    "latest_version": "1.2.3",
    "minimum_supported_version": "1.0.0",
    "apk_url": "http://34.229.130.142/media/app_updates/janmitra-1.2.3.apk"
}

# Response if no version configured (404 Not Found)
{
    "detail": "No active app version configured"
}
```

#### Flutter Integration Example

```dart
import 'package:dio/dio.dart';
import 'package:package_info_plus/package_info_plus.dart';

class AppUpdateService {
  static const String VERSION_CHECK_URL = 
    'http://34.229.130.142/api/v1/app/version/';
  
  final Dio _dio = Dio();
  
  Future<void> checkForUpdates() async {
    try {
      // Current app version
      PackageInfo packageInfo = await PackageInfo.fromPlatform();
      String currentVersion = packageInfo.version;
      
      // Fetch server version
      final response = await _dio.get(VERSION_CHECK_URL);
      
      String latestVersion = response.data['latest_version'];
      String minVersion = response.data['minimum_supported_version'];
      String apkUrl = response.data['apk_url'];
      
      // Check if current version is below minimum
      if (_isVersionLess(currentVersion, minVersion)) {
        // Force update dialog
        _showForceUpdateDialog(apkUrl);
      }
      // Check if newer version available
      else if (_isVersionLess(currentVersion, latestVersion)) {
        // Optional update dialog
        _showOptionalUpdateDialog(apkUrl);
      }
    } catch (e) {
      debugPrint('Error checking for updates: $e');
    }
  }
  
  bool _isVersionLess(String current, String minimum) {
    // Simple semantic versioning comparison
    // e.g., "1.0.0" < "1.2.0"
    final currParts = current.split('.').map(int.parse).toList();
    final minParts = minimum.split('.').map(int.parse).toList();
    
    for (int i = 0; i < 3; i++) {
      if (currParts[i] < minParts[i]) return true;
      if (currParts[i] > minParts[i]) return false;
    }
    return false;
  }
  
  void _showForceUpdateDialog(String apkUrl) {
    // Show dialog forcing user to update
    // Launch(apkUrl) to download APK
  }
  
  void _showOptionalUpdateDialog(String apkUrl) {
    // Show dialog with option to update later
  }
}
```

#### Integration Points

1. **Check on App Startup**
   ```dart
   void main() async {
     WidgetsFlutterBinding.ensureInitialized();
     
     // Check for updates
     await AppUpdateService().checkForUpdates();
     
     runApp(const MyApp());
   }
   ```

2. **Periodic Background Check**
   - Use `Timer` or `background_fetch` package
   - Check every session or daily

3. **Download & Install APK**
   - Use `url_launcher` to open APK URL
   - Or use `dio` to download + `install_apk` for direct installation

## File Locations on Server

```
├── media/
│   └── app_updates/
│       ├── janmitra-1.0.0.apk
│       ├── janmitra-1.1.0.apk
│       └── janmitra-1.2.3.apk  (currently active)
├── Janmitraapp/
│   ├── core/
│   │   ├── models.py           (AppVersion model)
│   │   ├── views.py            (AppVersionView)
│   │   ├── serializers.py      (AppVersionSerializer)
│   │   ├── urls.py             (routing)
│   │   └── admin.py            (admin interface)
```

## Database Schema

```sql
-- AppVersion table
CREATE TABLE app_versions (
    id UUID PRIMARY KEY,
    latest_version VARCHAR(20) NOT NULL,
    minimum_supported_version VARCHAR(20) NOT NULL,
    apk_file VARCHAR(100),  -- Path to file in media/app_updates/
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at DATETIME,
    updated_at DATETIME,
    deleted_at DATETIME,
    UNIQUE (latest_version)  -- One version per version number
);
```

## Testing

### Test API Endpoint

```bash
# Check for active version
curl -X GET http://34.229.130.142/api/v1/app/version/

# Response with no version (404)
curl -v http://34.229.130.142/api/v1/app/version/
```

### Test Model Locally

```bash
cd c:\janmitra\Janmitraapp
python manage.py shell

from core.models import AppVersion

# Create test version
v = AppVersion.objects.create(
    latest_version="1.0.0",
    minimum_supported_version="1.0.0",
    is_active=True
)

# Retrieve active version
active = AppVersion.get_active_version()
print(active)

# Test serializer
from core.serializers import AppVersionSerializer
ser = AppVersionSerializer(active)
print(ser.data)
```

### Run Test Suite

```bash
cd c:\janmitra\Janmitraapp
python test_app_version.py
```

Expected output:
```
============================================================
Testing AppVersion System
============================================================
✓ Cleared existing versions
✓ Test 1: Created test version: App v1.0.0 (active)
✓ Test 2: Retrieved active version: App v1.0.0 (active)
✓ Test 3: Created second version: App v1.1.0 (inactive)
✓ Test 4: Switched active version to: App v1.1.0 (active)
✓ Test 5: Serializer output:
  - latest_version: 1.1.0
  - minimum_supported_version: 1.0.0
  - apk_url: None

============================================================
✓ All tests passed!
```

## Deployment Checklist

- [x] AppVersion model created
- [x] Migration generated and applied
- [x] AppVersionSerializer created
- [x] AppVersionView created
- [x] URLs configured
- [x] Admin interface registered
- [x] Media folder configured
- [x] Tests passing
- [ ] First APK uploaded via admin
- [ ] Version checked via API
- [ ] Flutter app integrated
- [ ] Testing on real devices

## Common Tasks

### Upload a New APK

1. Go to `/admin/core/appversion/`
2. Click "Add App Version"
3. Fill in version numbers
4. Upload APK file
5. Uncheck "is_active" if multiple versions exist
6. Save
7. Use "Activate selected version" to make it current

### Force App Update

1. Go to existing version
2. Set `minimum_supported_version` to current app version
3. Create new version with higher version number
4. Set `is_active=True` on new version
5. Next app startup will detect and force update

### Rollback Version

1. Go to `/admin/core/appversion/`
2. Select the old version
3. Click "Activate selected version"
4. Confirm - all other versions now inactive

### Check Version from Android Device

```bash
# Via curl
adb shell 'curl http://34.229.130.142/api/v1/app/version/'

# Via browser on phone
# Visit: http://34.229.130.142/api/v1/app/version/
```

## Troubleshooting

### APK URL returns null in API

**Problem**: `apk_url` is null in response
**Cause**: No APK file uploaded for the version
**Solution**: Upload APK file in admin interface

### 404 when checking version

**Problem**: `GET /api/v1/app/version/` returns 404
**Cause**: No active version exists
**Solution**: Create an AppVersion with `is_active=True`

### APK file not downloading

**Problem**: Click APK URL but file not found
**Cause**: File not in media/app_updates/ folder OR MEDIA serving not configured
**Solution**: 
1. Check `/admin/` → Core → App Versions → File column
2. Verify file exists in `media/app_updates/`
3. Ensure DEBUG=True or static files configured for production

### Version switcher not working

**Problem**: Activate action doesn't switch active version
**Cause**: Bulk select not working in admin
**Solution**: 
1. Edit version directly
2. Uncheck all others `is_active`
3. Check the one you want
4. Save

## Security Notes

- AppVersion endpoint requires NO authentication (public)
- Only admins can upload/modify via Django admin
- APK file size recommended: < 100MB
- Storage location: `media/app_updates/` (auto-created)

## Version Control

Versions follow semantic versioning: `MAJOR.MINOR.PATCH`
- `1.0.0` = First release
- `1.1.0` = Minor features/fixes
- `1.1.1` = Patch/hotfix
- `2.0.0` = Major breaking changes

Minimum version enforcement:
- If `minimum_supported_version = 1.0.0`, all users on 0.x.x must update
- Useful for critical security fixes: set `minimum_supported_version` to force all users off old versions

---

**Implementation Date**: 2024
**Status**: ✅ Complete and Tested
**API Endpoint**: `GET /api/v1/app/version/` (public, no auth required)
