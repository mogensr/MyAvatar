# 🛡️ MyAvatar Disaster-Proof Local Backup Script
# PowerShell script for Windows local backups

param(
    [string]$BackupType = "full",
    [string]$BackupLocation = "C:\MyAvatar_Backups",
    [switch]$Compress = $true,
    [switch]$Verify = $true
)

# Configuration
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackupDate = Get-Date -Format "yyyyMMdd_HHmmss"
$CommitHash = & git -C $ProjectRoot rev-parse HEAD
$CommitShort = & git -C $ProjectRoot rev-parse --short HEAD
$BackupName = "MyAvatar_BACKUP_${BackupDate}_${CommitShort}"
$BackupPath = Join-Path $BackupLocation $BackupName

Write-Host "🛡️ MyAvatar Disaster-Proof Backup System" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Backup Type: $BackupType" -ForegroundColor Yellow
Write-Host "Backup Date: $BackupDate" -ForegroundColor Yellow
Write-Host "Commit Hash: $CommitHash" -ForegroundColor Yellow
Write-Host "Backup Path: $BackupPath" -ForegroundColor Yellow
Write-Host ""

# Create backup directory
if (!(Test-Path $BackupLocation)) {
    New-Item -ItemType Directory -Path $BackupLocation -Force | Out-Null
    Write-Host "✅ Created backup location: $BackupLocation" -ForegroundColor Green
}

New-Item -ItemType Directory -Path $BackupPath -Force | Out-Null
Write-Host "✅ Created backup directory: $BackupPath" -ForegroundColor Green

# Critical files and directories to backup
$CriticalItems = @(
    "main.py",
    "requirements.txt",
    "app\",
    "templates\",
    "static\",
    "portal\",
    "alembic\",
    "migrations\",
    ".github\",
    "*.md",
    "Dockerfile*",
    "railway.toml",
    "alembic.ini",
    ".env.template"
)

Write-Host "📦 Backing up critical files..." -ForegroundColor Yellow

foreach ($item in $CriticalItems) {
    $sourcePath = Join-Path $ProjectRoot $item
    $destinationPath = Join-Path $BackupPath $item
    
    if ($item.Contains("*")) {
        # Handle wildcards
        $files = Get-ChildItem -Path $ProjectRoot -Filter $item -ErrorAction SilentlyContinue
        foreach ($file in $files) {
            Copy-Item -Path $file.FullName -Destination $BackupPath -Force -ErrorAction SilentlyContinue
            if ($?) {
                Write-Host "  ✅ $($file.Name)" -ForegroundColor Green
            }
        }
    } elseif (Test-Path $sourcePath) {
        if (Test-Path $sourcePath -PathType Container) {
            # Directory
            Copy-Item -Path $sourcePath -Destination $BackupPath -Recurse -Force -ErrorAction SilentlyContinue
        } else {
            # File
            Copy-Item -Path $sourcePath -Destination $BackupPath -Force -ErrorAction SilentlyContinue
        }
        
        if ($?) {
            Write-Host "  ✅ $item" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  $item (failed)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ⚠️  $item (not found)" -ForegroundColor Yellow
    }
}

# Create backup manifest
$manifest = @{
    backup_date = $BackupDate
    commit_hash = $CommitHash
    commit_short = $CommitShort
    backup_type = $BackupType
    created_by = "PowerShell Disaster-Proof Backup"
    restore_instructions = "Use git checkout $CommitHash or copy files manually"
    backup_location = $BackupPath
    project_root = $ProjectRoot
} | ConvertTo-Json -Depth 3

$manifestPath = Join-Path $BackupPath "BACKUP_MANIFEST.json"
$manifest | Out-File -FilePath $manifestPath -Encoding UTF8
Write-Host "✅ Created backup manifest" -ForegroundColor Green

# Create restore script
$restoreScript = @"
@echo off
echo 🛡️ MyAvatar Disaster Recovery - Restore Script
echo ==============================================
echo Backup Date: $BackupDate
echo Commit Hash: $CommitHash
echo.
echo OPTION 1: Git Restore (Recommended)
echo git checkout $CommitHash
echo.
echo OPTION 2: File Restore
echo xcopy /E /Y app ..\app\
echo xcopy /E /Y templates ..\templates\
echo xcopy /E /Y static ..\static\
echo xcopy /E /Y portal ..\portal\
echo copy /Y main.py ..\
echo copy /Y requirements.txt ..\
echo.
echo OPTION 3: Complete Reset
echo git reset --hard $CommitHash
echo git push origin main --force
echo.
echo ⚠️  Always test in development environment first!
pause
"@

$restoreScriptPath = Join-Path $BackupPath "RESTORE.bat"
$restoreScript | Out-File -FilePath $restoreScriptPath -Encoding ASCII
Write-Host "✅ Created restore script" -ForegroundColor Green

# Compress backup if requested
if ($Compress) {
    Write-Host "📦 Compressing backup..." -ForegroundColor Yellow
    $zipPath = "$BackupPath.zip"
    Compress-Archive -Path $BackupPath -DestinationPath $zipPath -Force
    
    if (Test-Path $zipPath) {
        $zipSize = (Get-Item $zipPath).Length / 1MB
        Write-Host "✅ Compressed backup created: $zipPath ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor Green
        
        # Remove uncompressed backup
        Remove-Item -Path $BackupPath -Recurse -Force
    } else {
        Write-Host "❌ Compression failed" -ForegroundColor Red
    }
}

# Verify backup if requested
if ($Verify) {
    Write-Host "🔍 Verifying backup..." -ForegroundColor Yellow
    
    $backupToVerify = if ($Compress) { $zipPath } else { $BackupPath }
    
    if ($Compress) {
        # Extract and verify
        $tempVerifyPath = Join-Path $env:TEMP "backup_verify_$BackupDate"
        Expand-Archive -Path $zipPath -DestinationPath $tempVerifyPath -Force
        $verifyPath = Join-Path $tempVerifyPath $BackupName
    } else {
        $verifyPath = $BackupPath
    }
    
    # Check critical files
    $criticalFiles = @("main.py", "requirements.txt", "BACKUP_MANIFEST.json", "RESTORE.bat")
    $verificationPassed = $true
    
    foreach ($file in $criticalFiles) {
        $filePath = Join-Path $verifyPath $file
        if (Test-Path $filePath) {
            Write-Host "  ✅ $file" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $file (missing)" -ForegroundColor Red
            $verificationPassed = $false
        }
    }
    
    # Clean up temp verification
    if ($Compress -and (Test-Path $tempVerifyPath)) {
        Remove-Item -Path $tempVerifyPath -Recurse -Force
    }
    
    if ($verificationPassed) {
        Write-Host "✅ Backup verification successful!" -ForegroundColor Green
    } else {
        Write-Host "❌ Backup verification failed!" -ForegroundColor Red
        exit 1
    }
}

# Cleanup old backups (keep last 10)
Write-Host "🧹 Cleaning up old backups..." -ForegroundColor Yellow
$existingBackups = Get-ChildItem -Path $BackupLocation -Filter "MyAvatar_BACKUP_*" | Sort-Object CreationTime -Descending
if ($existingBackups.Count -gt 10) {
    $backupsToDelete = $existingBackups | Select-Object -Skip 10
    foreach ($backup in $backupsToDelete) {
        Remove-Item -Path $backup.FullName -Recurse -Force
        Write-Host "  🗑️  Removed old backup: $($backup.Name)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "🎉 Backup completed successfully!" -ForegroundColor Green
Write-Host "📍 Backup location: $backupToVerify" -ForegroundColor Cyan
Write-Host ""
Write-Host "🚀 Quick restore commands:" -ForegroundColor Yellow
Write-Host "  git checkout $CommitHash" -ForegroundColor White
Write-Host "  git reset --hard $CommitHash && git push origin main --force" -ForegroundColor White
Write-Host ""
