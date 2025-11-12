# PowerShell script to update environment variables for all Cloud Run services
$PROJECT_ID = "amadds102025"
$REGION = "us-west1"

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

$envVars = "SERVICE_API_KEY=test-api-key-12345,FMP_API_KEY=vcS4GLjpRr6YPgpYrwzM6BwZJHAcl3M0,RAG_CORPUS_ID=2305843009213693952,GCS_BUCKET=amadds102025-rag-documents,VERTEX_PROJECT=amadds102025,VERTEX_LOCATION=us-west1,PROJECT_ID=amadds102025"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Updating Environment Variables" -ForegroundColor Cyan
Write-Host "Region: $REGION" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

foreach ($service in $services) {
    Write-Host "Updating $service..." -ForegroundColor Yellow
    
    gcloud run services update $service `
        --region $REGION `
        --update-env-vars $envVars
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ $service updated successfully" -ForegroundColor Green
    } else {
        Write-Host "✗ $service update failed" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Environment Variables Update Complete!" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
