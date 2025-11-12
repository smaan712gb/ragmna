# PowerShell script to deploy all services to Cloud Run
$PROJECT_ID = "amadds102025"
$REGION = "us-west1"
$REGISTRY = "gcr.io/$PROJECT_ID"

$services = @(
    "data-ingestion",
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

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Deploying All Services to Cloud Run" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "Region: $REGION" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

foreach ($service in $services) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "Processing: $service" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    
    # Navigate to service directory
    Set-Location "services/$service"
    
    Write-Host "Building Docker image..." -ForegroundColor Yellow
    $imageName = "$REGISTRY/${service}:latest"
    docker build -t $imageName .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed for $service" -ForegroundColor Red
        Set-Location ../..
        continue
    }
    
    Write-Host "Pushing to Container Registry..." -ForegroundColor Yellow
    docker push $imageName
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Push failed for $service" -ForegroundColor Red
        Set-Location ../..
        continue
    }
    
    # Return to root
    Set-Location ../..
    
    Write-Host "Deploying to Cloud Run..." -ForegroundColor Yellow
    gcloud run deploy $service `
        --image $imageName `
        --region $REGION `
        --platform managed `
        --allow-unauthenticated `
        --memory 2Gi `
        --timeout 300s `
        --min-instances 0 `
        --max-instances 10 `
        --set-env-vars "PROJECT_ID=$PROJECT_ID,VERTEX_PROJECT=$PROJECT_ID,VERTEX_LOCATION=$REGION"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ $service deployed successfully" -ForegroundColor Green
    } else {
        Write-Host "✗ $service deployment failed" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
