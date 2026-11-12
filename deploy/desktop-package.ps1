# FabBot 桌面应用一键打包 (前端 + sidecar + C# 壳 + 组装部署目录)
# 用法: powershell -ExecutionPolicy Bypass -File deploy\desktop-package.ps1 [-Version 4.3.0]
param([string]$Version = "4.3.0")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== 1/5 前端构建 =="
Push-Location desktop\ui
npm ci 2>$null; if ($LASTEXITCODE -ne 0) { npm install }
npm run build
if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
Pop-Location

Write-Host "== 2/5 后端 sidecar (PyInstaller) =="
python -m PyInstaller --noconfirm --clean --onedir --name FabBotBackend `
  --paths . --collect-all uvicorn --collect-all app `
  --add-data "data/knowledge;bundle/knowledge" `
  --add-data "config.yaml;bundle" `
  --add-data "desktop/ui/dist;ui_dist" `
  backend_runner.py
if ($LASTEXITCODE -ne 0) { throw "sidecar 打包失败" }

Write-Host "== 3/5 C# 壳 (dotnet publish) =="
Push-Location desktop\shell
dotnet publish -c Release -o ..\..\dist\publish\shell
if ($LASTEXITCODE -ne 0) { throw "C# 构建失败" }
Pop-Location

Write-Host "== 4/5 组装 dist\FabBot-$Version =="
$out = "dist\FabBot-$Version"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force -Path "$out\backend" | Out-Null
Copy-Item dist\publish\shell\* $out -Recurse -Force
Copy-Item dist\FabBotBackend "$out\backend\FabBotBackend" -Recurse -Force

Write-Host "== 5/5 冒烟检查 =="
$env:FABBOT_PORT = "8119"
$proc = Start-Process -FilePath "$out\backend\FabBotBackend\FabBotBackend.exe" -PassThru `
  -WorkingDirectory "$out\backend\FabBotBackend" -WindowStyle Hidden
Start-Sleep -Seconds 12
$health = try { (Invoke-WebRequest "http://127.0.0.1:8119/api/health" -UseBasicParsing).Content } catch { "FAIL" }
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
if ($health -notmatch '"status":"ok"') { throw "冒烟检查失败: $health" }
Write-Host "冒烟通过: $health"
Write-Host ""
Write-Host "打包完成: $out"
Write-Host "双击 FabBot.exe 即用 (自动拉起后端 sidecar)"
