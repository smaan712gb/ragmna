# Configure IAM permissions for Cloud Run services to access Vertex AI RAG Engine
$PROJECT_ID = "amadds102025"
$REGION = "us-west1"
$SERVICE_ACCOUNT = "rag-service-account@amadds102025.iam.gserviceaccount.com"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Configuring RAG Engine Permissions" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Grant Vertex AI User role
Write-Host "Granting Vertex AI User role..." -ForegroundColor Yellow
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$SERVICE_ACCOUNT" `
    --role="roles/aiplatform.user"

# Grant Vertex AI Service Agent role  
Write-Host "Granting Vertex AI Service Agent role..." -ForegroundColor Yellow
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$SERVICE_ACCOUNT" `
    --role="roles/aiplatform.serviceAgent"

# Grant Storage Object Admin (for RAG corpus data)
Write-Host "Granting Storage Object Admin role..." -ForegroundColor Yellow
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$SERVICE_ACCOUNT" `
    --role="roles/storage.objectAdmin"

# Grant Cloud Run Invoker (for service-to-service calls)
Write-Host "Granting Cloud Run Invoker role..." -ForegroundColor Yellow
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$SERVICE_ACCOUNT" `
    --role="roles/run.invoker"

# Update ALL Cloud Run services to use this service account
$services = @(
    "data-ingestion",
    "financial-normalizer",
    "three-statement-modeler",
    "dcf-valuation",
    "cca-valuation",
    "lbo-analysis",
    "mergers-model",
    "dd-agent",
    "precedent-transactions",
    "board-reporting",
    "excel-exporter",
    "qa-engine",
    "run-manager",
    "llm-orchestrator",
    "reporting-dashboard"
)

Write-Host "`nUpdating Cloud Run services to use service account..." -ForegroundColor Yellow

foreach ($service in $services) {
    Write-Host "  Updating $service..." -ForegroundColor Gray
    gcloud run services update $service `
        --region $REGION `
        --service-account $SERVICE_ACCOUNT
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ $service updated" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $service update failed" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "RAG Permissions Configured!" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Wait 2-3 minutes for permissions to propagate" -ForegroundColor White
Write-Host "2. Run: python TEST_FULL_MA_WORKFLOW.py" -ForegroundColor White
Write-Host "3. RAG Engine should work without warnings" -ForegroundColor White
