---
name: janmitra-flutter
description: "JanMitra Flutter mobile development workflow. Use when building screens, providers, widgets, or integrating with the backend API in the unified Flutter app (janmitra_mobile)."
---

# JanMitra Flutter Development

## When to Use This Skill

- Building a new screen or feature in `janmitra_mobile/`
- Adding a Provider or modifying state management
- Integrating with a new backend API endpoint
- Debugging Flutter UI or navigation issues
- Reviewing Dart code for architecture violations

## App Architecture

ONE unified app for ALL users. Role-based routing after login.

```
janmitra_mobile/lib/
├── main.dart                        — Firebase init, Provider setup, offline init
├── core/
│   ├── constants/
│   │   ├── api_constants.dart       — All API endpoint URLs
│   │   └── user_roles.dart          — Role constants + normalization
│   ├── di/dependency_injection.dart — ALL providers wired here
│   ├── router/app_router.dart       — Role → route mapping
│   ├── network/
│   │   └── authenticated_http_client.dart — JWT auto-refresh
│   ├── services/
│   │   ├── location_service.dart
│   │   ├── location_resolver.dart   — GPS → area_name/city/state
│   │   ├── secure_media_service.dart
│   │   ├── fcm_notification_service.dart
│   │   └── secure_storage_service.dart
│   └── offline/                     — Draft storage, network monitor
└── features/
    ├── auth/
    ├── splash/
    ├── dashboard/
    ├── broadcast/                   — Citizen incident submission
    ├── reports/                     — Citizen case tracking (legacy path)
    └── incidents/                   — Authority case management
        ├── domain/entities + repositories (abstract)
        ├── data/datasources + repositories (impl) + models
        └── presentation/screens + providers + widgets
```

## Procedure for a New Screen

### 1. Create Feature Directory

```
features/<feature>/
├── domain/
│   ├── entities/<entity>.dart
│   └── repositories/<repo>.dart          ← abstract
├── data/
│   ├── datasources/<name>_datasource.dart
│   ├── repositories/<name>_repository_impl.dart
│   └── models/<entity>_model.dart
└── presentation/
    ├── screens/<name>_screen.dart
    ├── providers/<name>_provider.dart
    └── widgets/
```

### 2. Datasource Pattern

```dart
class MyDatasource {
  final AuthenticatedHttpClient _client;
  MyDatasource(this._client);

  Future<MyModel> fetchSomething(String caseId) async {
    final response = await _client.get(
      Uri.parse('${ApiConstants.baseUrl}/api/v1/cases/$caseId/something/'),
    );
    if (response.statusCode == 200) {
      return MyModel.fromJson(jsonDecode(response.body));
    }
    throw ServerException('Failed: ${response.statusCode}');
  }
}
```

### 3. Provider Pattern

```dart
class MyProvider extends ChangeNotifier {
  final MyRepository _repo;
  bool isLoading = false;
  String? errorMessage;

  MyProvider(this._repo);

  Future<void> load(String caseId) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();
    try {
      // await _repo.fetch(caseId);
    } catch (e) {
      errorMessage = e.toString();
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }
}
```

### 4. Register in DI

```dart
// core/di/dependency_injection.dart
ChangeNotifierProvider(create: (_) => MyProvider(MyRepositoryImpl(MyDatasource(client)))),
```

### 5. Add Route

```dart
// core/router/app_router.dart
case '/my-new-route':
  // role guard
  if (role == UserRoles.L2) return MyNewScreen();
  return UnauthorizedScreen();
```

### 6. Mandatory UI Rules

- `SafeArea` wraps all scrollable content
- `UserRoles.displayName(role)` for all role labels — never hardcode
- Show loading indicator during async calls
- Show error message on failure with retry option
- Follow existing screen layouts (see `incidents/presentation/screens/`)

## Build & Deploy

```bash
cd janmitra_mobile

flutter analyze        # Static analysis (must pass)
flutter test           # Unit tests
flutter build apk --debug

# Deploy to device
adb install -r build\app\outputs\flutter-apk\app-debug.apk
adb reverse tcp:8000 tcp:8000   # Physical device port-forward
```

Target: Samsung S24 Ultra (device ID: `RZCY10L1SLA`)  
ADB: `C:\Users\daved\AppData\Local\Android\Sdk\platform-tools\adb.exe`

## Role → Dashboard Routing

| Role | Route | Screen |
|------|-------|--------|
| JANMITRA | /janmitra-dashboard | JanMitraDashboard |
| L0 | /level0-dashboard | AuthorityCaseListScreen |
| L1 | /level1-dashboard | AuthorityCaseListScreen |
| L2 | /level2-dashboard | CaseListScreen |
| L3/L4 | /level2-captain-dashboard | CaptainCaseListScreen |

## Absolute Rules

- Never modify `mobile/` (deprecated)
- Never create separate apps per role
- Never hardcode role strings — use `UserRoles` constants
- Never use `CaseStatus.OPEN` in new code
- Never skip `SafeArea` on scrollable screens
