$ErrorActionPreference = 'Stop'
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) 'frontend')
$Host.UI.RawUI.WindowTitle = 'CTMS Frontend - React :5173'
& node '.\node_modules\vite\bin\vite.js' --host 127.0.0.1
