You write production-ready Flutter code for JanMitra's unified mobile app.

## APP STRUCTURE
ONE app (`janmitra_mobile/`) serves ALL users: citizens (JANMITRA) and authority officers (L0-L4).
The `mobile/` directory is DEPRECATED — never modify it.

## ARCHITECTURE
```
janmitra_mobile/lib/
├── main.dart
├── core/
│   ├── constants/
│   │   ├── api_constants.dart     — All API endpoint URLs
│   │   └── user_roles.dart        — Role constants + normalization
│   ├── di/dependency_injection.dart — Provider DI wiring
│   ├── router/app_router.dart     — Role-based route mapping
│   ├── network/
│   │   └── authenticated_http_client.dart — JWT auto-refresh HTTP client
│   ├── services/
│   │   ├── location_service.dart  — GPS access
│   │   ├── location_resolver.dart — Reverse geocoding (lat/lng → area name)
│   │   ├── secure_media_service.dart — Media capture
│   │   ├── fcm_notification_service.dart — Push notifications
│   │   └── secure_storage_service.dart — Token storage
│   ├── errors/exceptions.dart     — ServerException, AuthException, etc.
│   └── offline/                   — Offline draft storage, network monitor
├── features/
│   ├── auth/                      — Login for all roles
│   ├── splash/                    — Auth check + role-based redirect
│   ├── dashboard/                 — JanMitra, L1, L2 dashboards
│   ├── broadcast/                 — Citizen incident submission (new workflow)
│   ├── reports/                   — Citizen report management (old workflow)
│   └── incidents/                 — Authority case management
│       ├── domain/
│       │   ├── entities/incident.dart
│       │   └── repositories/ (abstract interfaces)
│       ├── data/
│       │   ├── datasources/ (HTTP calls)
│       │   ├── repositories/ (implementations)
│       │   └── models/ (JSON mapping)
│       └── presentation/
│           ├── screens/
│           │   ├── case_detail_screen.dart          — L2 (PI) view
│           │   ├── authority_case_detail_screen.dart — L0/L1 view
│           │   ├── captain_case_detail_screen.dart   — L3/L4 view
│           │   ├── case_list_screen.dart             — L2 case list
│           │   ├── authority_case_list_screen.dart   — L0/L1 case list
│           │   └── captain_case_list_screen.dart     — L3/L4 case list
│           ├── providers/
│           │   ├── incident_provider.dart     — L2 actions (solve, close, notes)
│           │   ├── authority_provider.dart     — L0/L1 actions (assign, solve)
│           │   └── captain_provider.dart       — L3/L4 actions (forward, reject)
│           └── widgets/
│               ├── case_detail_content.dart    — Shared case detail layout
│               └── investigation_chat.dart     — Group chat widget
```

## ROLE-BASED ROUTING (app_router.dart)
```
JANMITRA → /janmitra-dashboard (submit incidents, track cases)
L0       → /level0-dashboard (AuthorityCaseListScreen)
L1       → /level1-dashboard (AuthorityCaseListScreen)
L2       → /level2-dashboard (CaseListScreen)
L3       → /level2-captain-dashboard (CaptainCaseListScreen)
L4       → /level2-captain-dashboard (CaptainCaseListScreen)
```
Role normalization in user_roles.dart handles legacy names (level_0 → L0, level_2_captain → L2).

## PROVIDERS
| Provider | Serves | Key Methods |
|----------|--------|-------------|
| AuthProvider | All | login(), logout(), checkAuthStatus() |
| BroadcastProvider | JANMITRA | broadcastIncident() with area_name/city/state + media |
| IncidentProvider | L2 | fetchIncidents(), solveIncident(), closeCase(), addNote() |
| AuthorityProvider | L0/L1 | assignOfficer(), solveIncident(), fetchOfficers() |
| CaptainProvider | L3/L4 | forwardCase(), rejectCase() |

## DATA FLOW (Clean Architecture)
Screen → Provider → Repository (abstract) → DataSource (HTTP) → Backend API
Each feature has: domain/ (entities + repo interface), data/ (impl + datasource), presentation/ (screens + providers)

## CASE DETAIL SCREENS
All use shared `CaseDetailContent` widget which renders:
Media gallery → Metadata card → Location → Escalation info → Investigation chat → Action buttons

Action buttons vary by role and case status:
- L0/L1: "Mark as Solved" (active cases only)
- L2: "Mark as Solved" (active) OR "Close Case" (solved only)
- L3/L4: "Forward" and "Reject"

## INVESTIGATION CHAT (investigation_chat.dart)
- Collapsed by default, tap header to expand
- Red animated pulsing dot when unread messages
- Group chat style: avatar circles, role-colored names, speech bubbles
- System messages shown as centered grey pills
- Auto-scrolls to bottom
- Sends via POST /cases/{id}/messages/send/ with body: {text: "..."}

## CITIZEN SUBMISSION (broadcast/)
- GPS location captured automatically (mandatory)
- LocationResolver reverse geocodes to area_name, city, state
- All three sent to backend alongside lat/lng
- Media files uploaded via multipart POST
- Offline draft storage for poor connectivity

## DEPENDENCY INJECTION (core/di/)
HttpClientHolder singleton provides authenticated HTTP client.
All providers/repos/datasources wired via Provider in main.dart.

## KEY PATTERNS
- Provider + ChangeNotifier for state management
- SafeArea wrapping for Android nav bar compatibility
- AuthenticatedHttpClient handles 401 → refresh → retry transparently
- Platform-aware base URL (10.0.2.2 for Android emulator, localhost for web)
- FCM token registered via /api/v1/auth/device-token/ after login

## BUILD & DEPLOY
```
cd janmitra_mobile
flutter build apk --debug
adb install -r build\app\outputs\flutter-apk\app-debug.apk
adb reverse tcp:8000 tcp:8000
```
Package: com.example.janmitra_mobile
Backend: http://localhost:8000

## DO NOT
- Modify the `mobile/` directory (it's deprecated)
- Create separate apps for different roles (ONE app, role-based routing)
- Hardcode role names in UI (use UserRoles.displayName())
- Skip SafeArea wrapping on scrollable content
- Use CaseStatus.OPEN in any new code (legacy)