# JanMitra Production Deployment Checklist

**Status**: All critical auth bugs fixed and pushed to GitHub  
**Latest Commit**: `b12de1a` — Fix seed_users: pop full_name and email before create_user()  
**Production Server**: AWS EC2 (34.229.130.142)  
**Deployment Date**: [User to fill]

---

## Part 1: Production Server Deployment (IMMEDIATE ACTIONS)

### Step 1: Pull Latest Code with Auth Fixes
SSH into your EC2 instance and run:

```bash
cd ~/janmitra
git pull origin main
```

**What this pulls:**
- ✅ TokenRefreshView fix: Catches TokenError, returns 401 instead of 500
- ✅ DeviceBoundTokenRefreshSerializer fix: Extract payload BEFORE token blacklist
- ✅ CORS fix: Added x-device-fingerprint to CORS_ALLOW_HEADERS
- ✅ seed_users fix: Pop full_name and email before create_user()

### Step 2: Rebuild Docker with Latest Code
```bash
docker compose down
docker compose up -d --build
```

**What this does:**
- Stops all containers (Django, PostgreSQL, Redis, Nginx)
- Rebuilds the Docker image with the latest code from GitHub
- Starts fresh containers with all fixes applied
- Database persists (PostgreSQL volume not deleted)

**Expected output:**
```
[+] Building 45.3s (18/18) FINISHED
[+] Running 4/4
  ✔ Container janmitra-postgres-1  Running
  ✔ Container janmitra-redis-1      Running
  ✔ Container janmitra-django-1     Running
  ✔ Container janmitra-nginx-1      Running
```

### Step 3: Verify Django is Running
```bash
docker compose logs django | tail -20
```

**Look for:** "Starting development server" OR "Waiting for requests"  
**DO NOT proceed** if you see errors in the logs.

### Step 4: Create Demo Users in Database
```bash
docker compose exec django python manage.py seed_users --force
```

**Expected output:**
```
  Created: janmitra_demo (level_3)
  Created: level2@janmitra.gov.in (level_2)
  Created: captain@janmitra.gov.in (level_2_captain)
  Created: level1@janmitra.gov.in (level_1)
  Created: level0@janmitra.gov.in (level_0)

Done! Created: 5, Updated: 0
```

**If you get "Exists: user@... — use --force to reset"**, it means users already exist. Re-run with `--force` or skip if you have production users.

---

## Part 2: Backend Authentication Verification

### Test 1: Login Endpoint (JanMitra Member)
```bash
curl -X POST http://34.229.130.142/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "janmitra_demo",
    "password": "Demo@123",
    "device_id": "test-device-001"
  }'
```

**Expected response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid-here",
    "identifier": "janmitra_demo",
    "role": "level_3"
  }
}
```

### Test 2: Login Endpoint (Authority - Level 2)
```bash
curl -X POST http://34.229.130.142/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "level2@janmitra.gov.in",
    "password": "Level2@123",
    "device_id": "test-device-002"
  }'
```

**Expected response (200 OK):** Same format as above, role = "level_2"

### Test 3: Token Refresh with Device Binding
```bash
# First, get tokens from Test 1
ACCESS_TOKEN="<token from Test 1>"
DEVICE_FP="<device fingerprint from Flutter>"

# Then refresh with device binding header
curl -X POST http://34.229.130.142/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Fingerprint: $DEVICE_FP" \
  -d "{\"refresh\": \"$REFRESH_TOKEN\"}"
```

**Expected response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**If you get 401 Unauthorized:** Device fingerprint doesn't match. This is expected — Flutter generates its own device fingerprint on first launch.

### Test 4: CORS Preflight Check
```bash
curl -X OPTIONS http://34.229.130.142/api/v1/auth/login/ \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: X-Device-Fingerprint"
```

**Expected response (200 OK):**
```
Access-Control-Allow-Headers: X-Device-Fingerprint, Content-Type, ...
Access-Control-Allow-Origin: *
```

---

## Part 3: Flutter App Testing (Production)

### Update Flutter to Production Server
Edit [janmitra_mobile/lib/core/constants/api_constants.dart](janmitra_mobile/lib/core/constants/api_constants.dart#L1):

```dart
// PRODUCTION
static const String baseUrl = 'http://34.229.130.142';

// For HTTPS in the future:
// static const String baseUrl = 'https://34.229.130.142';
```

**Then rebuild the app:**
```bash
cd janmitra_mobile
flutter clean
flutter pub get
flutter run -d <device_id>
```

### Test Scenarios on Flutter App

#### Scenario 1: JanMitra Member Login
1. Launch app → Login screen
2. Enter: `janmitra_demo` / `Demo@123`
3. Tap "Login"
4. **Expected:** Home screen appears, shows "JanMitra Member"

#### Scenario 2: Authority Login (Level 2)
1. Logout (if already logged in)
2. Login with: `level2@janmitra.gov.in` / `Level2@123`
3. Tap "Login"
4. **Expected:** Home screen appears, shows "Authority (Level 2)"

#### Scenario 3: Token Expiry & Refresh
1. Login with any account
2. Wait 5 minutes (or simulate token expiry)
3. Try any API action (submit report, view case, etc.)
4. **Expected:** 
   - App auto-refreshes token (no 401 to user)
   - API action succeeds
   - No "Login expired" message

#### Scenario 4: Device Binding
1. Login on Device A
2. Get device fingerprint from logcat: `flutter logs | grep -i device`
3. Copy the same identifier/password to Device B
4. Login on Device B with same account
5. **Expected:** 
   - Device B login succeeds (new fingerprint)
   - Device A can still use old session
   - Both devices have their own tokens

---

## Part 4: All User Roles Testing

### Demo Users Created
| Identifier | Password | Role | Can Submit | Can Review | Can Escalate |
|------------|----------|------|-----------|-----------|------------|
| janmitra_demo | Demo@123 | JanMitra (L3) | ✅ | ❌ | ❌ |
| level2@janmitra.gov.in | Level2@123 | Field Officer (L2) | ❌ | ✅ | ✅ |
| captain@janmitra.gov.in | Captain@123 | L2 Captain | ❌ | ✅ | ✅ |
| level1@janmitra.gov.in | Level1@123 | Senior Authority (L1) | ❌ | ✅ | ✅ |
| level0@janmitra.gov.in | Level0@123 | Super Admin (L0) | ❌ | ✅ | ✅ |

**Test:** Login as each user, verify correct permissions on home screen.

---

## Part 5: Critical Bug Fixes Applied

### Bug #1: TokenRefreshView doesn't catch TokenError
- **File**: [backend/authentication/views.py](backend/authentication/views.py#L320)
- **Issue**: When token is malformed, TokenError thrown → 500 error
- **Fix**: Added try/except block, returns 401 Unauthorized
- **Impact**: Users can properly refresh or logout on 401

### Bug #2: Payload extracted after token blacklist
- **File**: [backend/authentication/serializers.py](backend/authentication/serializers.py#L436)
- **Issue**: Extract device fingerprint from payload AFTER super().validate() blacklists the token
- **Fix**: Extract payload BEFORE calling super().validate()
- **Impact**: Device binding validation works on token refresh

### Bug #3: CORS doesn't allow X-Device-Fingerprint header
- **File**: [backend/janmitra_backend/settings.py](backend/janmitra_backend/settings.py#L388)
- **Issue**: Flutter sends X-Device-Fingerprint header, but not in CORS_ALLOW_HEADERS
- **Fix**: Added 'x-device-fingerprint' to CORS_ALLOW_HEADERS list
- **Impact**: Preflight requests succeed, device binding header accepted

### Bug #4: No startup config visibility
- **File**: [backend/janmitra_backend/settings.py](backend/janmitra_backend/settings.py#L440)
- **Issue**: No logging of CORS config at startup
- **Fix**: Added startup logging block to print active configuration
- **Impact**: Can verify config is correct without code inspection

### Bug #5: seed_users passes invalid fields to User model
- **File**: [backend/authentication/management/commands/seed_users.py](backend/authentication/management/commands/seed_users.py#L80)
- **Issue**: full_name and email don't exist on User model, cause TypeError
- **Fix**: Pop these fields before calling create_user()
- **Impact**: Demo user creation works on first run

---

## Part 6: Post-Deployment Verification Checklist

### Database
- [ ] PostgreSQL container running: `docker compose ps`
- [ ] 5 demo users created: `docker compose exec django python manage.py shell`
  ```python
  from authentication.models import User
  print(User.objects.count())  # Should print 5
  ```
- [ ] No duplicate users (check `identifier` is unique)

### Backend APIs
- [ ] Login returns 200 with tokens
- [ ] Token refresh returns 200 with new access token
- [ ] Invalid credentials return 401
- [ ] Missing device_id in login returns 400
- [ ] Invalid token in refresh returns 401

### Flutter Client
- [ ] Login works with production IP
- [ ] Device fingerprint persists across app restarts
- [ ] Token refresh happens transparently on 401
- [ ] Logout clears device fingerprint and tokens
- [ ] Can submit incident as JanMitra member
- [ ] Can view cases as Level 2 officer

### Security
- [ ] Device binding prevents cross-device token reuse
- [ ] Token refresh requires device fingerprint header
- [ ] CORS allows only whitelisted origins
- [ ] Passwords are hashed in database (never plaintext)
- [ ] No errors leak sensitive info to logs

### Monitoring
- [ ] Check Django logs for errors: `docker compose logs django`
- [ ] Check Nginx access logs: `docker compose logs nginx`
- [ ] Check PostgreSQL logs: `docker compose logs postgres`
- [ ] Monitor disk space: `df -h`
- [ ] Monitor memory: `free -h`

---

## Part 7: Troubleshooting Common Issues

### Issue: "Invalid credentials" for all users after seed_users
**Cause**: Users weren't actually created (seed_users failed silently)  
**Solution**:
```bash
docker compose logs django | grep -i "seed_users\|ERROR"
docker compose exec django python manage.py seed_users --force
```

### Issue: Flutter gets 401 on every refresh
**Cause**: Device fingerprint doesn't match what server expects  
**Solution**:
- Logout on Flutter app (clears local device fingerprint)
- Login again (generates new device fingerprint)
- Device binding matches new fingerprint

### Issue: CORS preflight returns 403
**Cause**: Origin not whitelisted OR x-device-fingerprint not in CORS_ALLOW_HEADERS  
**Solution**:
```bash
docker compose logs nginx | grep "CORS\|403"
# Check .env file has correct CORS_ALLOWED_ORIGINS
```

### Issue: Docker rebuild takes too long
**Cause**: Downloading dependencies, caching disabled  
**Solution**:
```bash
# Use --no-cache only if necessary (slower)
docker compose up -d --build

# Or build separately then start
docker compose build --no-cache
docker compose up -d
```

### Issue: PostgreSQL won't start ("port 5432 in use")
**Cause**: Old container still running  
**Solution**:
```bash
docker ps -a
docker rm <container_id>  # Remove stopped container
docker compose up -d
```

---

## Part 8: Next Steps

### Immediate (Today)
1. ✅ Run Docker rebuild and seed_users
2. ✅ Test all 5 users can login via curl
3. ✅ Test Flutter app login on production IP
4. ✅ Verify device binding works

### Short Term (This Week)
1. [ ] Test incident submission end-to-end
2. [ ] Test case escalation workflow
3. [ ] Test media upload and encryption
4. [ ] Load test with multiple concurrent users

### Medium Term (This Month)
1. [ ] Setup HTTPS with SSL certificate
2. [ ] Configure domain name (instead of IP)
3. [ ] Setup monitoring & alerting (Prometheus/Grafana)
4. [ ] Configure automated backups for PostgreSQL
5. [ ] Create production user management dashboard

### Long Term
1. [ ] Flutter APK signing and Play Store submission
2. [ ] iOS app TestFlight distribution
3. [ ] Multi-region deployment
4. [ ] API rate limiting and DDoS protection

---

## Support & Reference

**GitHub Repository**: https://github.com/dhruvindave007/janmitra.git

**Commit History** (Recent fixes):
- `b12de1a` — Fix seed_users: pop full_name and email before create_user()
- `0cef080` — fix: seed_users command — pop all fields before unpacking to create_user()
- `f3d427f` — fix: Critical production auth + CORS fixes for Docker deployment
- `7651c24` — feat: Add seed_users management command for demo/production user creation
- `ad9de10` — chore: Update janmitra_mobile submodule to production API URL

**Files Modified** (In this debugging session):
- `backend/authentication/views.py` — TokenRefreshView exception handling
- `backend/authentication/serializers.py` — Payload extraction timing
- `backend/janmitra_backend/settings.py` — CORS headers and startup logging
- `backend/authentication/management/commands/seed_users.py` — Field popping fix
- `janmitra_mobile/lib/core/constants/api_constants.dart` — Production API URL
- `.env.example` — CORS configuration

**Key Documentation**:
- Authentication flow: [backend/authentication/README.md](backend/authentication/README.md) (if exists)
- Device binding: [backend/authentication/models.py#L411](backend/authentication/models.py#L411) (DeviceSession model)
- User roles: [backend/authentication/models.py#L30](backend/authentication/models.py#L30) (UserRole constants)

---

**Document Version**: 1.0  
**Last Updated**: [Auto-generated on deployment]  
**Created By**: GitHub Copilot + User Session  
**Status**: READY FOR PRODUCTION DEPLOYMENT
