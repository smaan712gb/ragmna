#!/bin/bash
# Deploy M&A Platform to Google Cloud Platform
# Usage: ./deploy-to-gcp.sh YOUR_PROJECT_ID YOUR_REGION

set -e

PROJECT_ID=$1
REGION=${2:-us-west1}

if [ -z "$PROJECT_ID" ]; then
    echo "Usage: ./deploy-to-gcp.sh YOUR_PROJECT_ID [REGION]"
    echo "Example: ./deploy-to-gcp.sh my-ma-platform us-west1"
    exit 1
fi

echo "🚀 Deploying M&A Platform to GCP"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Enable APIs
echo "📦 Enabling required GCP APIs..."
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage.googleapis.com

# Services to deploy
SERVICES=(
    "fmp-api-proxy:8000"
    "data-ingestion:8001"
    "llm-orchestrator:8002"
    "financial-normalizer:8003"
    "three-statement-modeler:8004"
    "dcf-valuation:8005"
    "cca-valuation:8006"
    "lbo-analysis:8007"
    "mergers-model:8008"
    "precedent-transactions:8009"
    "dd-agent:8010"
    "board-reporting:8011"
    "excel-exporter:8012"
    "run-manager:8013"
    "qa-engine:8014"
    "reporting-dashboard:8015"
    "auth-service:8016"
)

echo "📊 Deploying 17 microservices..."
echo ""

# Deploy each service
for service_port in "${SERVICES[@]}"; do
    service="${service_port%%:*}"
    port="${service_port##*:}"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔨 Building and deploying $service (port $port)..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    cd services/$service
    
    # Build and push
    echo "  📦 Building container..."
    gcloud builds submit --tag gcr.io/$PROJECT_ID/$service --quiet
    
    # Deploy to Cloud Run
    echo "  🚀 Deploying to Cloud Run..."
    gcloud run deploy $service \
        --image gcr.io/$PROJECT_ID/$service \
        --platform managed \
        --region $REGION \
        --allow-unauthenticated \
        --memory 2Gi \
        --cpu 1 \
        --timeout 300s \
        --max-instances 10 \
        --port 8080 \
        --quiet
    
    cd ../..
    
    echo "  ✅ $service deployed successfully"
    echo ""
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 ALL 17 SERVICES DEPLOYED TO CLOUD RUN!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Get service URLs:"
echo "   gcloud run services list --platform managed --region $REGION"
echo ""
echo "2. Update .env with Cloud Run URLs for inter-service communication"
echo ""
echo "3. Get llm-orchestrator URL for frontend:"
echo "   gcloud run services describe llm-orchestrator --platform managed --region $REGION --format='value(status.url)'"
echo ""
echo "4. Deploy frontend with backend URL:"
echo "   cd frontend"
echo "   echo 'NEXT_PUBLIC_API_BASE_URL=<llm-orchestrator-url>' > .env.production"
echo "   vercel --prod"
echo ""
echo "5. Test authentication:"
echo "   AUTH_URL=\$(gcloud run services describe auth-service --platform managed --region $REGION --format='value(status.url)')"
echo "   curl -X POST \$AUTH_URL/auth/login -H 'Content-Type: application/json' -d '{\"email\":\"admin@example.com\",\"password\":\"admin123\"}'"
echo ""
echo "6. Test M&A analysis through your frontend"
echo ""
echo "🔐 SECURITY REMINDER:"
echo "   - Change default admin password immediately"
echo "   - Generate new JWT_SECRET_KEY for production"
echo "   - Configure ALLOWED_ORIGINS for your production domain"
echo ""
