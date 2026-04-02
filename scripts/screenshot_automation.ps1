# =============================================================================
# JanMitra Screenshot Automation Script
# =============================================================================
# Automates Flutter app screenshots using Flutter Driver and integration tests
# =============================================================================

param(
    [string]$Device = "emulator",
    [switch]$AllScreens
)

$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\janmitra"
$ScreenshotDir = "$ProjectRoot\test-reports\screenshots"
$MobileDir = "$ProjectRoot\mobile"

function Write-Success { Write-Host "✓ $args" -ForegroundColor Green }
function Write-Error { Write-Host "✗ $args" -ForegroundColor Red }
function Write-Info { Write-Host "ℹ $args" -ForegroundColor Cyan }

# Create screenshot directory
New-Item -ItemType Directory -Force -Path $ScreenshotDir | Out-Null

Write-Info "Starting screenshot automation..."
Write-Info "Screenshots will be saved to: $ScreenshotDir"

Set-Location $MobileDir

# Check if Flutter is available
if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Error "Flutter is not installed or not in PATH"
    exit 1
}

# Check for connected devices
Write-Info "Checking for connected devices..."
$devices = flutter devices
Write-Host $devices

if ($devices -match "No devices detected") {
    Write-Warning "No devices connected. Please connect a device or start an emulator."
    Write-Info "To start an emulator, run: flutter emulators --launch <emulator_id>"
    Write-Info "To list available emulators, run: flutter emulators"
    exit 1
}

# Get dependencies
Write-Info "Getting Flutter dependencies..."
flutter pub get

# Create integration test if it doesn't exist
$integrationTestDir = "$MobileDir\integration_test"
$integrationTestFile = "$integrationTestDir\screenshot_test.dart"

if (-not (Test-Path $integrationTestDir)) {
    New-Item -ItemType Directory -Force -Path $integrationTestDir | Out-Null
}

# Create screenshot integration test
$screenshotTestContent = @'
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

// Import your app's main file
// import 'package:your_app/main.dart' as app;

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  
  group('Screenshot Tests', () {
    testWidgets('Capture Login Screen', (tester) async {
      // TODO: Launch your app
      // app.main();
      // await tester.pumpAndSettle();
      
      // Take screenshot
      await binding.convertFlutterSurfaceToImage();
      await tester.pumpAndSettle();
      
      // Save screenshot
      await takeScreenshot(tester, binding, 'login_screen');
    });
    
    testWidgets('Capture Home Screen', (tester) async {
      // TODO: Navigate to home screen
      // await tester.tap(find.byType(ElevatedButton));
      // await tester.pumpAndSettle();
      
      // Take screenshot
      await takeScreenshot(tester, binding, 'home_screen');
    });
  });
}

Future<void> takeScreenshot(
  WidgetTester tester,
  IntegrationTestWidgetsFlutterBinding binding,
  String screenshotName,
) async {
  await binding.convertFlutterSurfaceToImage();
  await tester.pumpAndSettle();
  
  // The screenshot will be saved automatically
  print('Screenshot taken: $screenshotName');
}
'@

if (-not (Test-Path $integrationTestFile)) {
    Write-Info "Creating integration test file..."
    $screenshotTestContent | Out-File -FilePath $integrationTestFile -Encoding UTF8
    Write-Success "Created $integrationTestFile"
}

# Update pubspec.yaml to include integration_test dependency
$pubspecPath = "$MobileDir\pubspec.yaml"
$pubspecContent = Get-Content $pubspecPath -Raw

if ($pubspecContent -notmatch "integration_test:") {
    Write-Info "Adding integration_test dependency to pubspec.yaml..."
    
    # Add to dev_dependencies
    $pubspecContent = $pubspecContent -replace "(dev_dependencies:)", "`$1`n  integration_test:`n    sdk: flutter"
    $pubspecContent | Out-File -FilePath $pubspecPath -Encoding UTF8 -NoNewline
    
    # Run pub get again
    flutter pub get
    Write-Success "Added integration_test dependency"
}

Write-Info "Screenshot test setup complete!"
Write-Info ""
Write-Info "To run screenshot tests:"
Write-Info "1. Start your app or emulator"
Write-Info "2. Run: flutter test integration_test/screenshot_test.dart"
Write-Info ""
Write-Info "Note: You'll need to customize the screenshot_test.dart file to match your app's structure"

# Alternative: Use adb to take screenshots if app is running
Write-Info ""
Write-Info "Alternative: Taking screenshot via ADB (if Android device connected)..."

try {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $screenshotPath = "/sdcard/screenshot_$timestamp.png"
    $localPath = "$ScreenshotDir\android_screen_$timestamp.png"
    
    # Take screenshot using adb
    adb shell screencap -p $screenshotPath
    
    if ($LASTEXITCODE -eq 0) {
        # Pull screenshot to local machine
        adb pull $screenshotPath $localPath
        
        # Clean up device screenshot
        adb shell rm $screenshotPath
        
        if (Test-Path $localPath) {
            Write-Success "Screenshot saved to: $localPath"
        }
    }
} catch {
    Write-Warning "ADB screenshot failed. Make sure an Android device/emulator is connected."
}

Set-Location $ProjectRoot
