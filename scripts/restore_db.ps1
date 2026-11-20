# Restore a backup made by backup_db.ps1  (WARNING: replaces current data)
# Usage: .\scripts\restore_db.ps1 -File .\backups\arbuilders_2026-11-11_2200.dump
param(
    [Parameter(Mandatory = $true)][string]$File,
    [string]$DbName = "arbuilders",
    [string]$DbUser = "postgres",
    [string]$DbHost = "localhost"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$line = Select-String -Path (Join-Path $root "backend\.env") -Pattern '^DB_PASSWORD=' | Select-Object -First 1
if ($line) { $env:PGPASSWORD = $line.Line.Split('=', 2)[1] }
$pgRestore = (Get-Command pg_restore -ErrorAction SilentlyContinue).Source
if (-not $pgRestore) {
    $pgRestore = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\pg_restore.exe" | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
$confirm = Read-Host "This will overwrite database '$DbName'. Type YES to continue"
if ($confirm -ne "YES") { Write-Host "Cancelled."; exit }
& $pgRestore -h $DbHost -U $DbUser -d $DbName --clean --if-exists --no-owner $File
Write-Host "Restore complete."
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
