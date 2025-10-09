param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"

# 1) создать venv если нет
if (-not (Test-Path ".venv")) {
  py -3 -m venv .venv
}

# 2) активировать
. .\.venv\Scripts\Activate.ps1

# 3) обновить pip и зависимости
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# 4) pre-commit
pre-commit install

Write-Host "`nBootstrap OK. Use:`n" -ForegroundColor Green
Write-Host "  .\\.venv\\Scripts\\Activate.ps1" -ForegroundColor Yellow
Write-Host "  python -m postavleno_bot.main" -ForegroundColor Yellow
Write-Host "  tools\\win\\tasks.ps1 test   # run checks" -ForegroundColor Yellow
