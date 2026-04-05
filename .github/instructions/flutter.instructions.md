---
description: "Use when writing, reviewing, or modifying Flutter/Dart mobile code. Covers Clean Architecture, Provider state management, role routing, API integration, and JanMitra-specific patterns."
applyTo: "janmitra_mobile/**"
---

# Flutter Instructions

Full Flutter practices → `.ai/skills/flutter.md`

## Core Constraints

- ONE app (`janmitra_mobile/`) for ALL users — never split by role
- `mobile/` is DEPRECATED — never modify it
- Clean Architecture per feature: `domain/` → `data/` → `presentation/`
- Provider + ChangeNotifier for all state management

## Role → Route Mapping (`core/router/app_router.dart`)

```
JANMITRA → /janmitra-dashboard   (submit incidents, track own cases)
L0       → /level0-dashboard     (AuthorityCaseListScreen)
L1       → /level1-dashboard     (AuthorityCaseListScreen)
L2       → /level2-dashboard     (CaseListScreen)
L3/L4    → /level2-captain-dashboard  (CaptainCaseListScreen)
```

Role normalization (legacy → canonical) is in `core/constants/user_roles.dart`.

## Provider Responsibilities

| Provider | Roles Served | Key Actions |
|----------|-------------|-------------|
| `AuthProvider` | All | `login()`, `logout()`, `checkAuthStatus()` |
| `BroadcastProvider` | JANMITRA | `broadcastIncident()` with area_name/city/state + media |
| `AuthorityProvider` | L0/L1 | `assignOfficer()`, `solveIncident()`, `fetchOfficers()` |
| `IncidentProvider` | L2 | `solveIncident()`, `closeCase()`, `addNote()` |
| `CaptainProvider` | L3/L4 | `forwardCase()`, `rejectCase()` |

## Key Patterns

- `AuthenticatedHttpClient` in `core/network/` handles JWT auto-refresh transparently
- `LocationResolver` in `core/services/` reverse-geocodes GPS → `area_name`, `city`, `state`; all three are sent to backend alongside lat/lng
- DI wired in `core/di/dependency_injection.dart` via Provider — register new providers there
- Offline drafts via `IncidentDraftStorage` in `core/offline/`
- FCM token registered via `POST /api/v1/auth/device-token/` after successful login

## UI Rules

- Wrap all scrollable content in `SafeArea`
- Use `UserRoles.displayName()` for labels — never hardcode role strings
- Case detail screens share `CaseDetailContent` widget
- Investigation chat: collapsed by default, red animated dot for unread messages

## New Feature Structure

```
features/<feature>/
├── domain/
│   ├── entities/<entity>.dart
│   └── repositories/<repo>.dart         ← abstract interface
├── data/
│   ├── datasources/<name>_datasource.dart
│   ├── repositories/<name>_repository_impl.dart
│   └── models/<entity>_model.dart       ← JSON ↔ entity mapping
└── presentation/
    ├── screens/<name>_screen.dart
    ├── providers/<name>_provider.dart
    └── widgets/                          ← shared sub-widgets
```

## Build Commands (Windows)

```bash
cd janmitra_mobile
flutter analyze
flutter test
flutter build apk --debug
adb install -r build\app\outputs\flutter-apk\app-debug.apk
adb reverse tcp:8000 tcp:8000   # Physical device port forward
```

Target device: Samsung S24 Ultra (ID: RZCY10L1SLA)  
ADB path: `C:\Users\daved\AppData\Local\Android\Sdk\platform-tools\adb.exe`
