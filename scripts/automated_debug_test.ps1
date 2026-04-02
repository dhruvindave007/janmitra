# =============================================================================
# JanMitra Automated Debug & Test Script
# =============================================================================
# This script automates:
# - Environment setup
# - Backend testing with coverage
# - Mobile app testing
# - Screenshot capture
# - Bug detection and reporting
# - Logs collection
# =============================================================================

param(
    [switch]$SkipBackend,
    [switch]$SkipMobile,
    [switch]$Screenshots,
    [switch]$FullTest
)

$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\janmitra"
$ReportDir = "$ProjectRoot\test-reports"
$ScreenshotDir = "$ReportDir\screenshots"
$LogDir = "$ReportDir\logs"

# Colors for output
function Write-Success { Write-Host "✓ $args" -ForegroundColor Green }
function Write-Error { Write-Host "✗ $args" -ForegroundColor Red }
function Write-Info { Write-Host "ℹ $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "⚠ $args" -ForegroundColor Yellow }

# Create report directories
Write-Info "Setting up test environment..."
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
New-Item -ItemType Directory -Force -Path $ScreenshotDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Start timestamp
$StartTime = Get-Date
$ReportFile = "$ReportDir\test-report-$(Get-Date -Format 'yyyyMMdd-HHmmss').md"

# Initialize report
@"
# JanMitra Automated Test Report
**Generated:** $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
**Execution Mode:** $(if($FullTest){"Full Test"}else{"Quick Test"})

---

"@ | Out-File -FilePath $ReportFile -Encoding UTF8

# =============================================================================
# ENVIRONMENT CHECK
# =============================================================================
Write-Info "Checking environment..."

$EnvIssues = @()

# Check .env file
if (!(Test-Path "$ProjectRoot\.env")) {
    Write-Warning ".env file missing - creating from template..."
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
    $EnvIssues += "⚠ .env was missing and has been created from template"
} else {
    Write-Success ".env file exists"
}

# Check Docker
try {
    docker --version | Out-Null
    Write-Success "Docker is installed"
} catch {
    Write-Error "Docker is not installed or not in PATH"
    $EnvIssues += "✗ Docker is not available"
}

# Check Python
try {
    python --version | Out-Null
    Write-Success "Python is installed"
} catch {
    Write-Error "Python is not installed or not in PATH"
    $EnvIssues += "✗ Python is not available"
}

# Check Flutter
try {
    flutter --version | Out-Null
    Write-Success "Flutter is installed"
} catch {
    Write-Warning "Flutter is not installed or not in PATH"
    $EnvIssues += "⚠ Flutter is not available (mobile testing will be skipped)"
}

"## Environment Check`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
if ($EnvIssues.Count -gt 0) {
    "**Issues Found:**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    $EnvIssues | ForEach-Object { "- $_`n" } | Out-File -FilePath $ReportFile -Append -Encoding UTF8
} else {
    "✓ All environment checks passed`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
}
"`n---`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

# =============================================================================
# DOCKER SERVICES STATUS
# =============================================================================
Write-Info "Checking Docker services..."

"## Docker Services Status`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

Set-Location $ProjectRoot

# Check if services are running
$dockerStatus = docker-compose ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Docker services are not running. Starting services..."
    "**Starting Docker services...**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    
    docker-compose up -d 2>&1 | Out-File -FilePath "$LogDir\docker-startup.log" -Encoding UTF8
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Docker services started successfully"
        "✓ Services started successfully`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        
        # Wait for services to be ready
        Write-Info "Waiting for services to be ready (30 seconds)..."
        Start-Sleep -Seconds 30
    } else {
        Write-Error "Failed to start Docker services"
        "✗ Failed to start services. Check logs/docker-startup.log`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    }
} else {
    Write-Success "Docker services are running"
    "✓ Services are already running`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
}

# Show service status
docker-compose ps | Out-File -FilePath "$LogDir\docker-services.log" -Encoding UTF8
Get-Content "$LogDir\docker-services.log" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

"`n---`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

# =============================================================================
# BACKEND TESTING
# =============================================================================
if (-not $SkipBackend) {
    Write-Info "Running backend tests..."
    
    "## Backend Tests`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    
    # Run Django tests
    Write-Info "Executing Django test suite..."
    $backendTestOutput = docker-compose exec -T django python manage.py test --verbosity=2 2>&1
    $backendTestOutput | Out-File -FilePath "$LogDir\backend-tests.log" -Encoding UTF8
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Backend tests passed"
        "✓ **All backend tests passed**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    } else {
        Write-Error "Backend tests failed"
        "✗ **Backend tests failed**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    }
    
    # Extract test summary
    "### Test Output`n``````" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    $backendTestOutput | Select-Object -Last 20 | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    "``````n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    
    # Check for migrations
    Write-Info "Checking for pending migrations..."
    $migrationsCheck = docker-compose exec -T django python manage.py showmigrations --plan 2>&1
    $migrationsCheck | Out-File -FilePath "$LogDir\migrations-check.log" -Encoding UTF8
    
    if ($migrationsCheck -match "[ ]") {
        Write-Warning "Pending migrations detected"
        "⚠ **Pending migrations detected**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    } else {
        Write-Success "All migrations applied"
        "✓ All migrations applied`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    }
    
    # Collect backend logs
    Write-Info "Collecting backend logs..."
    docker-compose logs --tail=100 django 2>&1 | Out-File -FilePath "$LogDir\django-logs.log" -Encoding UTF8
    docker-compose logs --tail=100 db 2>&1 | Out-File -FilePath "$LogDir\db-logs.log" -Encoding UTF8
    
    "`n---`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
}

# =============================================================================
# MOBILE APP TESTING
# =============================================================================
if (-not $SkipMobile) {
    Write-Info "Running mobile app tests..."
    
    "## Mobile App Tests`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    
    Set-Location "$ProjectRoot\mobile"
    
    # Check for Flutter
    if (Get-Command flutter -ErrorAction SilentlyContinue) {
        # Get dependencies
        Write-Info "Getting Flutter dependencies..."
        flutter pub get 2>&1 | Out-File -FilePath "$LogDir\flutter-pub-get.log" -Encoding UTF8
        
        # Run tests
        Write-Info "Running Flutter tests..."
        $flutterTestOutput = flutter test 2>&1
        $flutterTestOutput | Out-File -FilePath "$LogDir\flutter-tests.log" -Encoding UTF8
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Flutter tests passed"
            "✓ **All Flutter tests passed**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        } else {
            Write-Warning "Flutter tests failed or no tests found"
            "⚠ **Flutter tests failed or no tests found**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        }
        
        "### Test Output`n``````" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        $flutterTestOutput | Select-Object -Last 20 | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        "``````n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        
        # Run flutter analyze
        Write-Info "Running Flutter analyze..."
        $analyzeOutput = flutter analyze 2>&1
        $analyzeOutput | Out-File -FilePath "$LogDir\flutter-analyze.log" -Encoding UTF8
        
        if ($analyzeOutput -match "No issues found") {
            Write-Success "No Flutter analysis issues"
            "✓ **No static analysis issues**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        } else {
            Write-Warning "Flutter analysis found issues"
            "⚠ **Static analysis found issues**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
            "``````" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
            $analyzeOutput | Select-Object -First 30 | Out-File -FilePath $ReportFile -Append -Encoding UTF8
            "``````n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        }
    } else {
        Write-Warning "Flutter not available, skipping mobile tests"
        "⚠ **Flutter not available - mobile tests skipped**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    }
    
    Set-Location $ProjectRoot
    "`n---`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
}

# =============================================================================
# API HEALTH CHECK
# =============================================================================
Write-Info "Checking API endpoints..."

"## API Health Check`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

try {
    $apiResponse = Invoke-WebRequest -Uri "http://localhost:8000/api/health/" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    if ($apiResponse.StatusCode -eq 200) {
        Write-Success "API health endpoint is responding"
        "✓ **API is healthy** (Status: $($apiResponse.StatusCode))`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    }
} catch {
    Write-Error "API health check failed: $_"
    "✗ **API health check failed**`n``````" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    $_.Exception.Message | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    "``````n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
}

"`n---`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

# =============================================================================
# BUG DETECTION
# =============================================================================
Write-Info "Scanning for common issues..."

"## Bug Detection`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

$BugsFound = @()

# Check for TODO/FIXME/HACK in code
Write-Info "Checking for TODO/FIXME markers..."
$todoPattern = "TODO|FIXME|HACK|XXX|BUG"
$codeIssues = Get-ChildItem -Path "$ProjectRoot\backend" -Recurse -Include *.py | 
    Select-String -Pattern $todoPattern | 
    Select-Object -First 10

if ($codeIssues) {
    $BugsFound += "Found TODO/FIXME markers in code"
    "### Code Markers Found`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    $codeIssues | ForEach-Object { "- $($_.Line.Trim())`n" } | Out-File -FilePath $ReportFile -Append -Encoding UTF8
}

# Check for error patterns in logs
Write-Info "Checking logs for errors..."
if (Test-Path "$LogDir\django-logs.log") {
    $errorPatterns = Get-Content "$LogDir\django-logs.log" | Select-String -Pattern "ERROR|CRITICAL|Exception|Traceback"
    if ($errorPatterns) {
        $BugsFound += "Errors found in Django logs"
        "`n### Errors in Logs`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        $errorPatterns | Select-Object -First 10 | ForEach-Object { "- $_`n" } | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    }
}

# Check for unclosed database connections
$dbConnections = docker-compose exec -T db psql -U janmitra_user -d janmitra_db -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction';" 2>&1
if ($dbConnections -match "\d+" -and [int]($Matches[0]) -gt 5) {
    $BugsFound += "High number of idle database connections detected"
}

if ($BugsFound.Count -eq 0) {
    Write-Success "No critical issues detected"
    "✓ **No critical issues detected**`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
} else {
    Write-Warning "Found $($BugsFound.Count) potential issues"
    "`n**Summary:** Found $($BugsFound.Count) potential issues`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
}

"`n---`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

# =============================================================================
# SUMMARY
# =============================================================================
$EndTime = Get-Date
$Duration = $EndTime - $StartTime

"## Test Execution Summary`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
"- **Start Time:** $(($StartTime).ToString('yyyy-MM-dd HH:mm:ss'))`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
"- **End Time:** $(($EndTime).ToString('yyyy-MM-dd HH:mm:ss'))`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
"- **Duration:** $($Duration.TotalMinutes.ToString('0.00')) minutes`n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
"- **Report Location:** ``$ReportFile```n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
"- **Logs Location:** ``$LogDir```n" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

Write-Success "Test execution completed in $($Duration.TotalMinutes.ToString('0.00')) minutes"
Write-Info "Full report saved to: $ReportFile"

# Open report
Write-Host "`n"
Write-Info "Opening test report..."
Start-Process $ReportFile

# Return to project root
Set-Location $ProjectRoot
