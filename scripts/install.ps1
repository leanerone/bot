# Fab Bot 一键安装 (Windows): venv + 依赖 + 启动提示
# 用法: powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> 创建虚拟环境 .venv"
if (-not (Test-Path ".venv")) { python -m venv .venv }

Write-Host "==> 安装依赖 (清华镜像)"
& .venv\Scripts\python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet

Write-Host "==> 运行测试 (自检)"
& .venv\Scripts\python -m pytest tests -q

Write-Host ""
Write-Host "安装完成。启动:"
Write-Host "  .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8100"
Write-Host "登录: http://127.0.0.1:8100 (admin / admin123, 首次登录后立即改密)"
