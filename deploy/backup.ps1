# Fab Bot 数据备份 (Windows 计划任务用)
# 用法: powershell -File deploy\backup.ps1 [备份目录, 默认 D:\fabbot-backup]
param([string]$Dest = "D:\fabbot-backup")
$src = Join-Path $PSScriptRoot "..\data"
if (-not (Test-Path $src)) { Write-Error "找不到数据目录 $src"; exit 1 }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$target = Join-Path $Dest $stamp
New-Item -ItemType Directory -Force -Path $target | Out-Null
# app.db 用 SQLite 在线备份方式最稳妥; 简化起见先整目录拷贝 (WAL 下建议停服或用 sqlite3 .backup)
Copy-Item -Recurse -Force $src $target
Write-Host "备份完成: $target"
# 保留最近 14 份
Get-ChildItem $Dest -Directory | Sort-Object Name | Select-Object -First ([Math]::Max(0, (Get-ChildItem $Dest -Directory).Count - 14)) | Remove-Item -Recurse -Force
