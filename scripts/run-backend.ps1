$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$Host.UI.RawUI.WindowTitle = 'CTMS Backend - Django :8000'
if (-not (Test-Path -LiteralPath '.env')) {
    $env:DJANGO_DEBUG = 'true'
    $env:DB_ENGINE = 'sqlite'
    Write-Warning 'No .env found. Using the existing local SQLite development database. MySQL remains unconfigured.'
}
& '.\.venv\Scripts\python.exe' -u manage.py runserver 127.0.0.1:8000 --noreload --nothreading
