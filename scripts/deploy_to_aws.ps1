# =============================================================================
# JANMITRA V1 - Deploy from Windows to AWS EC2
# Usage: .\scripts\deploy_to_aws.ps1 -ServerIP "YOUR_IP"
# =============================================================================
param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIP,
    
    [string]$KeyFile = "$env:USERPROFILE\Downloads\janmitra-server-key.pem",
    
    [string]$User = "ubuntu"
)

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  JANMITRA V1 - AWS DEPLOYMENT" -ForegroundColor Cyan
Write-Host "  Target: $User@$ServerIP" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Validate key file
if (-not (Test-Path $KeyFile)) {
    Write-Host "ERROR: PEM key not found at $KeyFile" -ForegroundColor Red
    exit 1
}

$SSH = "ssh -i `"$KeyFile`" -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL $User@$ServerIP"
$SCP = "scp -i `"$KeyFile`" -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL"

# Step 1: Test connectivity
Write-Host "[1/6] Testing SSH connection..." -ForegroundColor Yellow
$result = Invoke-Expression "$SSH echo 'connected'" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Cannot connect to $ServerIP" -ForegroundColor Red
    Write-Host "Make sure:" -ForegroundColor Red
    Write-Host "  - Instance is running" -ForegroundColor Red
    Write-Host "  - Security group allows port 22 from your IP" -ForegroundColor Red
    Write-Host "  - Key file is correct" -ForegroundColor Red
    exit 1
}
Write-Host "  Connected!" -ForegroundColor Green

# Step 2: Upload deploy script
Write-Host "[2/6] Uploading deploy script..." -ForegroundColor Yellow
Invoke-Expression "$SCP `"C:\janmitra\scripts\deploy_v1.sh`" $User@${ServerIP}:/tmp/deploy_v1.sh"
Write-Host "  Uploaded." -ForegroundColor Green

# Step 3: Make executable and run
Write-Host "[3/6] Running deployment on server (this takes 5-10 minutes)..." -ForegroundColor Yellow
Invoke-Expression "$SSH `"chmod +x /tmp/deploy_v1.sh && /tmp/deploy_v1.sh`""

# Step 4: Build Flutter web app locally
$FlutterAppDir = "C:\janmitra\janmitra_mobile"
$WebArchivePath = Join-Path $FlutterAppDir "build\webapp-deploy.tar.gz"

if (-not (Test-Path (Join-Path $FlutterAppDir "pubspec.yaml"))) {
    Write-Host "ERROR: Flutter app source not found at $FlutterAppDir" -ForegroundColor Red
    exit 1
}

Write-Host "`n[4/6] Building Flutter web app locally..." -ForegroundColor Yellow
Push-Location $FlutterAppDir
try {
    flutter pub get
    if ($LASTEXITCODE -ne 0) { throw "flutter pub get failed" }

    flutter build web --release --base-href /webapp/
    if ($LASTEXITCODE -ne 0) { throw "flutter build web failed" }

    if (Test-Path $WebArchivePath) {
        Remove-Item $WebArchivePath -Force
    }

    tar -czf $WebArchivePath -C (Join-Path $FlutterAppDir "build\web") .
    if ($LASTEXITCODE -ne 0) { throw "tar packaging failed" }
} finally {
    Pop-Location
}
Write-Host "  Web app built." -ForegroundColor Green

# Step 5: Upload published web app bundle
Write-Host "[5/6] Uploading web app bundle..." -ForegroundColor Yellow
Invoke-Expression "$SCP `"$WebArchivePath`" $User@${ServerIP}:/tmp/webapp-deploy.tar.gz"

$PublishWebCommand = 'set -e; sudo rm -rf /var/www/html/webapp.new; sudo mkdir -p /var/www/html/webapp.new; sudo tar -xzf /tmp/webapp-deploy.tar.gz -C /var/www/html/webapp.new; if [ -d /var/www/html/webapp ]; then sudo rm -rf /var/www/html/webapp.old; sudo mv /var/www/html/webapp /var/www/html/webapp.old; fi; sudo mv /var/www/html/webapp.new /var/www/html/webapp; sudo rm -rf /var/www/html/webapp.old; grep -n ''<base href="/webapp/">'' /var/www/html/webapp/index.html'
Invoke-Expression "$SSH `"$PublishWebCommand`""
Write-Host "  Web app published to /webapp/." -ForegroundColor Green

# Step 6: Verify
Write-Host "`n[6/6] Verifying deployment..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://${ServerIP}/health/" -TimeoutSec 10
    Write-Host "  Health check: OK" -ForegroundColor Green
} catch {
    Write-Host "  Health check: Could not reach (may need a moment)" -ForegroundColor Yellow
}

try {
    $version = Invoke-RestMethod -Uri "http://${ServerIP}/api/v1/app/version-check/" -TimeoutSec 10
    Write-Host "  Version API: $($version.latest_version)" -ForegroundColor Green
} catch {
    Write-Host "  Version API: Not yet reachable" -ForegroundColor Yellow
}

try {
    $webResponse = Invoke-WebRequest -Uri "http://${ServerIP}/webapp/" -TimeoutSec 10
    if ($webResponse.StatusCode -eq 200) {
        Write-Host "  Web app: Updated and reachable" -ForegroundColor Green
    } else {
        Write-Host "  Web app: Returned status $($webResponse.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  Web app: Not yet reachable" -ForegroundColor Yellow
}

if (Test-Path $WebArchivePath) {
    Remove-Item $WebArchivePath -Force
}

# Step 5: Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Admin:   http://$ServerIP/admin/" -ForegroundColor White
Write-Host "  API:     http://$ServerIP/api/v1/" -ForegroundColor White
Write-Host "  Web:     http://$ServerIP/webapp/" -ForegroundColor White
Write-Host "  Health:  http://$ServerIP/health/" -ForegroundColor White
Write-Host ""
Write-Host "  SSH:     ssh -i `"$KeyFile`" $User@$ServerIP" -ForegroundColor Gray
Write-Host "  Logs:    ssh ... 'cd /opt/janmitra && docker-compose logs -f'" -ForegroundColor Gray
Write-Host ""
