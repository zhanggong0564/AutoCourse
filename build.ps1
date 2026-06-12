$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m PyInstaller --noconfirm --clean auto-course-watcher.spec

Write-Host "构建完成：dist\自动看课助手.exe" -ForegroundColor Green
