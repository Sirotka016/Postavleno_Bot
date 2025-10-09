param(
  [ValidateSet("test","lint","type","all")]
  [string]$Task = "all"
)

$ErrorActionPreference = "Stop"

function Run-Test { pytest }
function Run-Type { mypy src }
function Run-Lint {
  black --check src tests
  ruff check src tests
}

switch ($Task) {
  "test" { Run-Test }
  "type" { Run-Type }
  "lint" { Run-Lint }
  "all"  { Run-Test; Run-Type; Run-Lint }
}
