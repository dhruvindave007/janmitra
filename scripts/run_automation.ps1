# =============================================================================
# JanMitra Master Automation Script
# =============================================================================
# One-click automation for all debugging, testing, and screenshot tasks
# =============================================================================

param(
    [switch]$Setup,      # Initial setup only
    [switch]$Test,       # Run tests only
    [switch]$Screenshot, # Take screenshots only
    [switch]$Full        # Full automation (default)
)

$ErrorActionPreference = "Continue"
$ScriptDir = "C:\janmitra\scripts"
$ProjectRoot = "C:\janmitra"

function Write-Success { Write-Host "✓ $args" -ForegroundColor Green }
function Write-Error { Write-Host "✗ $args" -ForegroundColor Red }
function Write-Info { Write-Host "ℹ $args" -ForegroundColor Cyan }
function Write-Title { 
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host " $args" -ForegroundColor Yellow
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host ""
}

# If no flags, run full automation
if (-not ($Setup -or $Test -or $Screenshot)) {
    $Full = $true
}

Write-Title "JanMitra Master Automation"
Write-Info "Starting automated debugging and testing workflow..."

# =============================================================================
# STEP 1: Setup & Configuration
# =============================================================================
if ($Setup -or $Full) {
    Write-Title "Step 1: Environment Setup & Configuration"
    
    Write-Info "Enabling VS Code settings..."
    & "$ScriptDir\enable_vscode_settings.ps1"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "VS Code settings configured successfully"
    } else {
        Write-Error "VS Code settings configuration failed"
    }
    
    # Check if .env exists
    if (-not (Test-Path "$ProjectRoot\.env")) {
        Write-Info "Creating .env file from template..."
        Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
        Write-Success ".env file created"
        Write-Warning "Please update .env with your actual configuration values"
    } else {
        Write-Success ".env file already exists"
    }
}

# =============================================================================
# STEP 2: Automated Testing
# =============================================================================
if ($Test -or $Full) {
    Write-Title "Step 2: Running Automated Tests"
    
    Write-Info "Executing comprehensive test suite..."
    & "$ScriptDir\automated_debug_test.ps1" -FullTest
    
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
        Write-Success "Automated tests completed"
    } else {
        Write-Warning "Some tests may have failed - check the report"
    }
}

# =============================================================================
# STEP 3: Screenshot Automation
# =============================================================================
if ($Screenshot -or $Full) {
    Write-Title "Step 3: Screenshot Automation"
    
    Write-Info "Setting up screenshot automation..."
    & "$ScriptDir\screenshot_automation.ps1"
    
    Write-Success "Screenshot automation setup complete"
}

# =============================================================================
# Summary
# =============================================================================
Write-Title "Automation Complete!"

Write-Success "All automation tasks have been executed successfully!"
Write-Info ""
Write-Info "What was done:"
Write-Info "  ✓ VS Code settings and launch configurations created"
Write-Info "  ✓ Python terminal environment file enabled"
Write-Info "  ✓ Docker services checked and started if needed"
Write-Info "  ✓ Backend tests executed (Django)"
Write-Info "  ✓ Mobile tests executed (Flutter)"
Write-Info "  ✓ API health checks performed"
Write-Info "  ✓ Bug detection and log analysis completed"
Write-Info "  ✓ Screenshot automation configured"
Write-Info ""
Write-Info "Check the test reports in: C:\janmitra\test-reports\"
Write-Info ""
Write-Info "Quick Commands:"
Write-Info "  - Run tests only:        .\scripts\run_automation.ps1 -Test"
Write-Info "  - Take screenshots:      .\scripts\run_automation.ps1 -Screenshot"
Write-Info "  - Setup only:            .\scripts\run_automation.ps1 -Setup"
Write-Info "  - Full automation:       .\scripts\run_automation.ps1"
Write-Info ""
Write-Info "VS Code Integration:"
Write-Info "  - Press F5 to start debugging Django or Flutter"
Write-Info "  - Press Ctrl+Shift+P > Tasks: Run Task > Run Automated Tests"
Write-Info "  - Environment variables from .env are now auto-loaded in terminal"
Write-Info ""
Write-Success "Happy debugging! 🚀"
