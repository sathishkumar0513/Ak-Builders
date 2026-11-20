# AK Builders - PostgreSQL backup for Windows (local install)
# Usage (PowerShell):  .\scripts\backup_db.ps1
# Schedule daily: Task Scheduler -> Create Basic Task -> Daily 10:00 PM ->
#   Program: powershell.exe   Arguments: -ExecutionPolicy Bypass -File "D:\new project\AK Builder\scripts\backup_db.ps1"

param(
    [string]$DbName = "arbuilders",
    [string]$DbUser = "postgres",
    [string]$DbHost = "localhost",
    [int]$KeepDays = 30
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $root "backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

# Read DB_PASSWORD from backend\.env so it is never hard-coded here
$envFile = Join-Path $root "backend\.env"
if (Test-Path $envFile) {
    $line = Select-String -Path $envFile -Pattern '^DB_PASSWORD=' | Select-Object -First 1
    if ($line) { $env:PGPASSWORD = $line.Line.Split('=', 2)[1] }
}

# Find pg_dump (adds the default PostgreSQL install folder if not on PATH)
$pgDump = (Get-Command pg_dump -ErrorAction SilentlyContinue).Source
if (-not $pgDump) {
    $pgDump = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\pg_dump.exe" | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $pgDump) { throw "pg_dump not found. Add PostgreSQL\bin to PATH." }

$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$file = Join-Path $backupDir "arbuilders_$stamp.dump"
& $pgDump -h $DbHost -U $DbUser -F c -Z 9 -f $file $DbName
Write-Host "Backup saved: $file"

# Delete backups older than $KeepDays days
Get-ChildItem $backupDir -Filter "arbuilders_*.dump" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } | Remove-Item
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
