#!/bin/bash
# Complete GCP Deployment Script for M&A Platform
# This deploys all 14 microservices to Google Cloud Run

set -e

# Configuration
PROJECT_ID="amadds102025"
REGION="us-west1"
REGISTRY="gcr.io/${PROJECT_ID}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "M&A Platform - GCP Deployment"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "=================================================="

# Set project
echo -e "${YELLOW}Setting GCP project...${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable \
    run.googleapis.com \
    containerregistry.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com \
    storage.googleapis.com

# Services to deploy
declare -a SERVICES=(
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
)

# Build and deploy each service
for SERVICE_PORT in "${SERVICES[@]}"; do
    IFS=':' read -r SERVICE PORT <<< "$SERVICE_PORT"
    
    echo ""
    echo "=================================================="
    echo -e "${GREEN}Processing: ${SERVICE}${NC}"
    echo "=================================================="
    
    # Navigate to service directory
    cd "services/${SERVICE}"
    
    # Build Docker image
    echo -e "${YELLOW}Building Docker image...${NC}"
    IMAGE_NAME="${REGISTRY}/${SERVICE}:latest"
    docker build -t ${IMAGE_NAME} .
    
    # Push to GCR
    echo -e "${YELLOW}Pushing to Container Registry...${NC}"
    docker push ${IMAGE_NAME}
    
    # Deploy to Cloud Run
    echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
    gcloud run deploy ${SERVICE} \
        --image ${IMAGE_NAME} \
        --region ${REGION} \
        --platform managed \
        --allow-unauthenticated \
        --memory 2Gi \
        --timeout 300s \
        --min-instances 0 \
        --max-instances 10 \
        --set-env-vars "PROJECT_ID=${PROJECT_ID},VERTEX_PROJECT=${PROJECT_ID},VERTEX_LOCATION=${REGION}"
    
    echo -e "${GREEN}✓ ${SERVICE} deployed successfully${NC}"
    
    # Return to root
    cd ../..
done

echo ""
echo "=================================================="
echo -e "${GREEN}ALL SERVICES DEPLOYED SUCCESSFULLY!${NC}"
echo "=================================================="

# Get service URLs
echo ""
echo "Service URLs:"
for SERVICE_PORT in "${SERVICES[@]}"; do
    IFS=':' read -r SERVICE PORT <<< "$SERVICE_PORT"
    URL=$(gcloud run services describe ${SERVICE} --region ${REGION} --format='value(status.url)')
    echo "  ${SERVICE}: ${URL}"
done

echo ""
echo -e "${GREEN}Deployment complete! Platform is ready for testing.${NC}"
