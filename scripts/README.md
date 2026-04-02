# JanMitra Automation Scripts - Quick Guide

This directory contains automated scripts for debugging, testing, and screenshot capture.

## 🚀 Quick Start

### Run Everything (Recommended for first time)
```powershell
.\scripts\run_automation.ps1
```

This will:
- ✓ Enable all VS Code settings automatically (including Python terminal .env file)
- ✓ Start Docker services if needed
- ✓ Run all backend tests (Django)
- ✓ Run all mobile tests (Flutter)
- ✓ Check API health
- ✓ Scan for bugs and issues
- ✓ Generate detailed test reports
- ✓ Setup screenshot automation
- ✓ Collect all logs

## 📋 Available Scripts

### 1. `run_automation.ps1` - Master Script
One command to run everything!

```powershell
# Run full automation
.\scripts\run_automation.ps1

# Setup only (VS Code settings, .env file)
.\scripts\run_automation.ps1 -Setup

# Run tests only
.\scripts\run_automation.ps1 -Test

# Setup screenshot automation only
.\scripts\run_automation.ps1 -Screenshot
```

### 2. `automated_debug_test.ps1` - Testing & Bug Detection
Comprehensive test runner with bug detection

```powershell
# Run all tests
.\scripts\automated_debug_test.ps1

# Skip backend tests
.\scripts\automated_debug_test.ps1 -SkipBackend

# Skip mobile tests
.\scripts\automated_debug_test.ps1 -SkipMobile

# Full test with coverage
.\scripts\automated_debug_test.ps1 -FullTest
```

**What it does:**
- ✓ Checks environment (Docker, Python, Flutter)
- ✓ Starts Docker services automatically
- ✓ Runs Django test suite
- ✓ Runs Flutter tests
- ✓ Checks API endpoints
- ✓ Scans code for TODO/FIXME/BUG markers
- ✓ Analyzes logs for errors
- ✓ Checks database connections
- ✓ Generates detailed markdown report
- ✓ Collects all logs in one place

### 3. `screenshot_automation.ps1` - Screenshot Capture
Automates screenshot capture for the mobile app

```powershell
# Setup screenshot automation
.\scripts\screenshot_automation.ps1

# Capture all screens
.\scripts\screenshot_automation.ps1 -AllScreens
```

**What it does:**
- ✓ Creates Flutter integration tests for screenshots
- ✓ Adds required dependencies
- ✓ Takes screenshots via ADB (Android)
- ✓ Saves screenshots to test-reports/screenshots/

### 4. `enable_vscode_settings.ps1` - VS Code Configuration
Automatically configures VS Code for the project

```powershell
.\scripts\enable_vscode_settings.ps1
```

**What it configures:**
- ✓ Python terminal environment file usage (`python.terminal.useEnvFile = true`)
- ✓ Python linting and formatting
- ✓ Flutter/Dart settings
- ✓ Debug configurations (F5 to debug)
- ✓ Tasks for quick testing
- ✓ File associations
- ✓ Auto-save and format on save

## 📊 Output & Reports

All automation outputs are saved to:
```
C:\janmitra\test-reports\
├── test-report-YYYYMMDD-HHMMSS.md    # Main test report
├── logs\                              # All collected logs
│   ├── backend-tests.log
│   ├── flutter-tests.log
│   ├── django-logs.log
│   ├── docker-services.log
│   └── ...
└── screenshots\                       # App screenshots
    └── ...
```

## 🔧 VS Code Integration

After running the automation, you can:

### Debug Django Backend
1. Press `F5`
2. Select "Python: Django"
3. Backend starts with debugger attached

### Debug Flutter App
1. Connect device or start emulator
2. Press `F5`
3. Select "Flutter: Debug"

### Run Tests via Tasks
1. Press `Ctrl+Shift+P`
2. Type "Tasks: Run Task"
3. Select:
   - "Run Automated Tests" (full automation)
   - "Run Backend Tests"
   - "Run Flutter Tests"
   - "Start Docker Services"
   - "Stop Docker Services"

## 🐛 Bug Detection Features

The automation automatically scans for:
- ✓ TODO, FIXME, HACK, BUG markers in code
- ✓ Errors and exceptions in logs
- ✓ Unclosed database connections
- ✓ Failed tests
- ✓ API endpoint failures
- ✓ Pending database migrations
- ✓ Flutter analysis issues

## 📸 Screenshot Automation

### For Android:
1. Connect Android device or start emulator
2. Run: `.\scripts\screenshot_automation.ps1`
3. Screenshots saved via ADB

### For iOS:
1. Screenshots via simulator: `xcrun simctl io booted screenshot screenshot.png`
2. Or use Flutter integration tests

### Customizing Screenshots:
Edit `mobile\integration_test\screenshot_test.dart` to:
- Navigate to specific screens
- Capture different states
- Take screenshots at key moments

## ⚙️ Automatic Permissions & Settings

The scripts automatically enable:
- ✅ Python terminal environment file injection
- ✅ Auto-formatting on save
- ✅ Linting for Python and Dart
- ✅ Test discovery
- ✅ Debug configurations
- ✅ .env file loading in terminals

**No manual configuration needed!**

## 🚦 Common Scenarios

### "I just cloned the repo, what do I do?"
```powershell
.\scripts\run_automation.ps1 -Setup
# Then update .env with your values
.\scripts\run_automation.ps1
```

### "I want to test before committing"
```powershell
.\scripts\run_automation.ps1 -Test
# Check the generated report
```

### "I need screenshots for documentation"
```powershell
# Start your app first
flutter run
# In another terminal:
.\scripts\screenshot_automation.ps1
```

### "VS Code says environment injection is disabled"
```powershell
.\scripts\enable_vscode_settings.ps1
# Reload VS Code window
```

## 📝 Requirements

- **Docker Desktop** - For backend services
- **Python 3.8+** - For Django
- **Flutter SDK** - For mobile app
- **VS Code** - For IDE integration
- **PowerShell 5.1+** - For running scripts

## 🔄 CI/CD Integration

These scripts can be integrated into your CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Run Automated Tests
  run: |
    powershell -ExecutionPolicy Bypass -File scripts/automated_debug_test.ps1 -FullTest
```

## 💡 Tips

1. **First Time Setup**: Run `.\scripts\run_automation.ps1` to configure everything
2. **Regular Testing**: Use `.\scripts\run_automation.ps1 -Test` before commits
3. **Debugging**: Press F5 in VS Code to start debugging with breakpoints
4. **Logs**: Always check `test-reports/logs/` for detailed information
5. **Screenshots**: Customize `integration_test/screenshot_test.dart` for your screens

## 🆘 Troubleshooting

### "Docker not found"
```powershell
# Install Docker Desktop for Windows
winget install Docker.DockerDesktop
```

### "Flutter not found"
```powershell
# Install Flutter
# Download from: https://flutter.dev/docs/get-started/install/windows
# Or use chocolatey:
choco install flutter
```

### "Execution policy error"
```powershell
# Run PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "Tests failing"
1. Check the test report in `test-reports/`
2. Look at logs in `test-reports/logs/`
3. Ensure Docker services are running: `docker-compose ps`
4. Verify .env file has correct values

## 📚 Additional Resources

- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [Flutter Testing Guide](https://flutter.dev/docs/testing)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

**Last Updated:** 2026-04-01
**Author:** Automated by GitHub Copilot
