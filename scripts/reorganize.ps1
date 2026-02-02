# PowerShell script to reorganize JanMitra for deployment
# Run this from c:\janmitra directory

Write-Host "========================================" -ForegroundColor Green
Write-Host "JANMITRA REPO REORGANIZATION" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Check if we're in the right directory
if (-not (Test-Path "Janmitraapp")) {
    Write-Host "ERROR: Run this script from c:\janmitra directory" -ForegroundColor Red
    exit 1
}

Write-Host "`nStep 1: Copying Django backend files..." -ForegroundColor Yellow

# Copy Django project files to backend/
$djangoFiles = @(
    "manage.py",
    "janmitra_backend",
    "authentication",
    "audit",
    "core",
    "escalation",
    "media_storage",
    "notifications",
    "reports"
)

foreach ($item in $djangoFiles) {
    $source = "Janmitraapp\$item"
    $dest = "backend\$item"
    
    if (Test-Path $source) {
        if (Test-Path $source -PathType Container) {
            # It's a directory
            if (Test-Path $dest) {
                Remove-Item -Path $dest -Recurse -Force
            }
            Copy-Item -Path $source -Destination $dest -Recurse -Force
            Write-Host "  Copied directory: $item" -ForegroundColor Cyan
        } else {
            # It's a file
            Copy-Item -Path $source -Destination $dest -Force
            Write-Host "  Copied file: $item" -ForegroundColor Cyan
        }
    } else {
        Write-Host "  WARNING: $source not found" -ForegroundColor Red
    }
}

Write-Host "`nStep 2: Copying Flutter mobile files..." -ForegroundColor Yellow

# Copy Flutter project to mobile/
if (Test-Path "janmitra_mobile") {
    if (Test-Path "mobile") {
        Remove-Item -Path "mobile" -Recurse -Force
    }
    Copy-Item -Path "janmitra_mobile" -Destination "mobile" -Recurse -Force
    Write-Host "  Copied Flutter project to mobile/" -ForegroundColor Cyan
}

Write-Host "`nStep 3: Cleaning up unnecessary files in backend..." -ForegroundColor Yellow

# Remove files that shouldn't be in production
$filesToRemove = @(
    "backend\*.sqlite3",
    "backend\*.db",
    "backend\__pycache__",
    "backend\*\__pycache__",
    "backend\*\migrations\__pycache__",
    "backend\venv",
    "backend\.venv",
    "backend\logs\*.log"
)

foreach ($pattern in $filesToRemove) {
    if (Test-Path $pattern) {
        Remove-Item -Path $pattern -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  Removed: $pattern" -ForegroundColor Cyan
    }
}

Write-Host "`nStep 4: Creating required directories..." -ForegroundColor Yellow

$dirsToCreate = @(
    "backend\logs",
    "backend\staticfiles",
    "backend\encrypted_media"
)

foreach ($dir in $dirsToCreate) {
    if (-not (Test-Path $dir)) {
        New-Item -Path $dir -ItemType Directory -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Cyan
    }
}

# Create .gitkeep files
"" | Out-File -FilePath "backend\logs\.gitkeep" -Encoding utf8
"" | Out-File -FilePath "backend\staticfiles\.gitkeep" -Encoding utf8
"" | Out-File -FilePath "backend\encrypted_media\.gitkeep" -Encoding utf8

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "REORGANIZATION COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nRepository structure:" -ForegroundColor White
Write-Host "  backend/     - Django REST API" -ForegroundColor Cyan
Write-Host "  mobile/      - Flutter mobile app" -ForegroundColor Cyan
Write-Host "  docker/      - Docker configurations" -ForegroundColor Cyan
Write-Host "  scripts/     - Deployment scripts" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor White
Write-Host "  1. Review .env.example and create .env" -ForegroundColor Yellow
Write-Host "  2. Initialize git: git init" -ForegroundColor Yellow
Write-Host "  3. Add remote: git remote add origin https://github.com/dhruvindave007/janmitra.git" -ForegroundColor Yellow
Write-Host "  4. Stage files: git add ." -ForegroundColor Yellow
Write-Host "  5. Commit: git commit -m 'Initial production deployment setup'" -ForegroundColor Yellow
Write-Host "  6. Push: git push -u origin main" -ForegroundColor Yellow
