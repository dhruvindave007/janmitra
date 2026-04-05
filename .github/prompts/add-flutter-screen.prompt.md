---
description: "Scaffold a new Flutter screen for JanMitra following Clean Architecture, Provider pattern, and role-based routing."
argument-hint: "Describe the screen: e.g. 'L2 audit trail screen showing CaseStatusHistory for a case'"
agent: "agent"
---

Scaffold a new Flutter screen for JanMitra's unified mobile app.

**Screen spec:** ${input}

Follow these rules exactly:

1. **Directory** — create files in `janmitra_mobile/lib/features/<feature>/`

2. **Clean Architecture structure:**
   ```
   domain/entities/<entity>.dart
   domain/repositories/<repo>.dart          ← abstract interface
   data/datasources/<name>_datasource.dart
   data/repositories/<name>_repository_impl.dart
   data/models/<entity>_model.dart          ← JSON ↔ entity mapping
   presentation/screens/<name>_screen.dart
   presentation/providers/<name>_provider.dart
   ```

3. **HTTP** — use `AuthenticatedHttpClient` (injected from `core/di/dependency_injection.dart`); it handles JWT auto-refresh automatically

4. **State** — use `Provider` + `ChangeNotifier`; add new provider registration in `core/di/dependency_injection.dart`

5. **Routing** — add the route to `core/router/app_router.dart` with appropriate role guard; follow the existing role → route pattern

6. **UI rules:**
   - Wrap all scrollable content in `SafeArea`
   - Use `UserRoles.displayName()` for role labels — never hardcode strings
   - Follow existing screen layouts: loading state, error state, content

7. **Never** — modify `mobile/` (deprecated), create role-specific apps, or use `CaseStatus.OPEN`

Output complete, working Dart code for all affected files — no placeholders, no TODOs.
