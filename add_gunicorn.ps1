# PowerShell script to add gunicorn to all requirements.txt files
$services = @(
    "financial-normalizer",
    "dd-agent",
    "board-reporting",
    "precedent-transactions",
    "run-manager",
    "qa-engine",
    "excel-exporter",
    "three-statement-modeler",
    "dcf-valuation",
    "cca-valuation",
    "lbo-analysis",
    "mergers-model",
    "reporting-dashboard"
)

foreach ($service in $services) {
    $reqFile = "services/$service/requirements.txt"
    if (Test-Path $reqFile) {
        $content = Get-Content $reqFile -Raw
        if ($content -notmatch "gunicorn") {
            # Find Flask line and add gunicorn after it
            $lines = Get-Content $reqFile
            $newLines = @()
            foreach ($line in $lines) {
                $newLines += $line
                if ($line -match "^[Ff]lask") {
                    $newLines += "gunicorn==21.2.0"
                }
            }
            $newLines | Set-Content $reqFile
            Write-Host "Added gunicorn to $service" -ForegroundColor Green
        } else {
            Write-Host "Gunicorn already in $service" -ForegroundColor Yellow
        }
    }
}
