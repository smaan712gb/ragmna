#!/bin/bash

# M&A Analysis Platform Deployment Script
set -e

echo "🚀 Starting M&A Analysis Platform Deployment"

# Activate conda environment
echo "🐍 Activating conda environment: ragmna"
conda activate ragmna || {
    echo "❌ Failed to activate conda environment. Please run:"
    echo "conda env create -f environment.yml"
    echo "conda activate ragmna"
    exit 1
}

# Configuration
PROJECT_ID=${PROJECT_ID:-"your-gcp-project"}
REGION=${REGION:-"us-central1"}
FMP_API_KEY=${FMP_API_KEY:-""}
SERVICE_API_KEY=${SERVICE_API_KEY:-""}
DB_PASSWORD=${DB_PASSWORD:-""}

if [ -z "$FMP_API_KEY" ] || [ -z "$SERVICE_API_KEY" ] || [ -z "$DB_PASSWORD" ]; then
    echo "❌ Error: Required environment variables not set"
    echo "Please set: FMP_API_KEY, SERVICE_API_KEY, DB_PASSWORD"
    exit 1
fi

echo "📋 Step 1: Setting up Terraform infrastructure..."
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Create terraform.tfvars
cat > terraform.tfvars << EOF
project_id = "${PROJECT_ID}"
region = "${REGION}"
db_password = "${DB_PASSWORD}"
EOF

# Plan and apply infrastructure
terraform plan -out=tfplan
terraform apply tfplan

echo "🔑 Step 2: Setting up secrets..."
# Store secrets in Secret Manager
echo -n "${FMP_API_KEY}" | gcloud secrets versions add fmp-api-key --data-file=-
echo -n "${SERVICE_API_KEY}" | gcloud secrets versions add service-api-key --data-file=-
echo -n "${DB_PASSWORD}" | gcloud secrets versions add db-password --data-file=-

echo "🐳 Step 3: Building and deploying services..."

# Build and push all services
echo "Building FMP API Proxy..."
cd ../../../services/fmp-api-proxy
gcloud builds submit --tag gcr.io/${PROJECT_ID}/fmp-api-proxy:latest .

echo "Building LLM Orchestrator..."
cd ../llm-orchestrator
gcloud builds submit --tag gcr.io/${PROJECT_ID}/llm-orchestrator:latest .

echo "Building 3-Statement Modeler..."
cd ../three-statement-modeler
gcloud builds submit --tag gcr.io/${PROJECT_ID}/three-statement-modeler:latest .

echo "Building DCF Valuation..."
cd ../dcf-valuation
gcloud builds submit --tag gcr.io/${PROJECT_ID}/dcf-valuation:latest .

echo "Building CCA Valuation..."
cd ../cca-valuation
gcloud builds submit --tag gcr.io/${PROJECT_ID}/cca-valuation:latest .

echo "Building LBO Analysis..."
cd ../lbo-analysis
gcloud builds submit --tag gcr.io/${PROJECT_ID}/lbo-analysis:latest .

echo "Building Mergers Model..."
cd ../mergers-model
gcloud builds submit --tag gcr.io/${PROJECT_ID}/mergers-model:latest .

echo "Building Due Diligence Agent..."
cd ../dd-agent
gcloud builds submit --tag gcr.io/${PROJECT_ID}/dd-agent:latest .

echo "Building Excel Exporter..."
cd ../excel-exporter
gcloud builds submit --tag gcr.io/${PROJECT_ID}/excel-exporter:latest .

echo "Building Reporting Dashboard..."
cd ../reporting-dashboard
gcloud builds submit --tag gcr.io/${PROJECT_ID}/reporting-dashboard:latest .

echo "Building Data Ingestion..."
cd ../data-ingestion
gcloud builds submit --tag gcr.io/${PROJECT_ID}/data-ingestion:latest .

echo "✅ Step 4: Running post-deployment setup..."

# Get service URLs
FMP_PROXY_URL=$(gcloud run services describe fmp-api-proxy --region=${REGION} --format="value(status.url)")
LLM_ORCHESTRATOR_URL=$(gcloud run services describe llm-orchestrator --region=${REGION} --format="value(status.url)")

echo "🌐 Service URLs:"
echo "FMP API Proxy: ${FMP_PROXY_URL}"
echo "LLM Orchestrator: ${LLM_ORCHESTRATOR_URL}"

echo "🧪 Step 5: Running health checks..."
# Health checks
curl -f ${FMP_PROXY_URL}/health
curl -f ${LLM_ORCHESTRATOR_URL}/health

echo "🎉 Deployment completed successfully!"
echo ""
echo "📖 Next steps:"
echo "1. Configure monitoring and alerting dashboards"
echo "2. Set up CI/CD pipelines for automated deployments"
echo "3. Implement Phase 3 features (real-time news, interactive dashboards, ML training)"
echo "4. Test end-to-end M&A analysis workflow"
echo ""
echo "🔗 API Documentation:"
echo "POST ${LLM_ORCHESTRATOR_URL}/analysis/ma"
echo 'Body: {"target_symbol": "AAPL", "acquirer_symbol": "MSFT"}'
echo ""
echo "📊 Available Services:"
echo "• FMP API Proxy: ${FMP_PROXY_URL}"
echo "• LLM Orchestrator: ${LLM_ORCHESTRATOR_URL}"
echo "• 3-Statement Modeler, DCF/CCA/LBO Valuation, Due Diligence Agent"
echo "• Excel Exporter, Reporting Dashboard, Data Ingestion, Mergers Model"
