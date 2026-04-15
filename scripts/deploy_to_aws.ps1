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
Write-Host "[1/5] Testing SSH connection..." -ForegroundColor Yellow
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
Write-Host "[2/5] Uploading deploy script..." -ForegroundColor Yellow
Invoke-Expression "$SCP `"C:\janmitra\scripts\deploy_v1.sh`" $User@${ServerIP}:/tmp/deploy_v1.sh"
Write-Host "  Uploaded." -ForegroundColor Green

# Step 3: Make executable and run
Write-Host "[3/5] Running deployment on server (this takes 5-10 minutes)..." -ForegroundColor Yellow
Invoke-Expression "$SSH `"chmod +x /tmp/deploy_v1.sh && /tmp/deploy_v1.sh`""

# Step 4: Verify
Write-Host "`n[4/5] Verifying deployment..." -ForegroundColor Yellow
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

# Step 5: Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Admin:   http://$ServerIP/admin/" -ForegroundColor White
Write-Host "  API:     http://$ServerIP/api/v1/" -ForegroundColor White
Write-Host "  Health:  http://$ServerIP/health/" -ForegroundColor White
Write-Host ""
Write-Host "  SSH:     ssh -i `"$KeyFile`" $User@$ServerIP" -ForegroundColor Gray
Write-Host "  Logs:    ssh ... 'cd /opt/janmitra && docker-compose logs -f'" -ForegroundColor Gray
Write-Host ""
