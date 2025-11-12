#!/bin/bash

# RAG Engine Setup Automation Script
# This script automates the setup of Vertex AI RAG Engine for M&A analysis

set -e

# Configuration - Set these environment variables or modify defaults
PROJECT_ID=${PROJECT_ID:-"amadds102025"}
LOCATION=${LOCATION:-"us-west1"}
CORPUS_DISPLAY_NAME=${CORPUS_DISPLAY_NAME:-"M&A Analysis Corpus"}
CORPUS_DESCRIPTION=${CORPUS_DESCRIPTION:-"RAG corpus for M&A due diligence and analysis"}
GCS_BUCKET=${GCS_BUCKET:-"amadds102025-rag-documents"}
SERVICE_ACCOUNT=${SERVICE_ACCOUNT:-"rag-service-account@amadds102025.iam.gserviceaccount.com"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting RAG Engine Setup...${NC}"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n 1 > /dev/null; then
    echo -e "${RED}Error: Not authenticated with gcloud. Please run 'gcloud auth login' first.${NC}"
    exit 1
fi

# Set project
echo -e "${YELLOW}Setting project to ${PROJECT_ID}...${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Create service account if it doesn't exist
echo -e "${YELLOW}Checking/creating service account...${NC}"
if ! gcloud iam service-accounts describe ${SERVICE_ACCOUNT} &> /dev/null; then
    gcloud iam service-accounts create rag-service-account \
        --description="Service account for RAG Engine operations" \
        --display-name="RAG Service Account"
    echo -e "${GREEN}Service account created.${NC}"
else
    echo -e "${GREEN}Service account already exists.${NC}"
fi

# Grant necessary permissions
echo -e "${YELLOW}Granting permissions to service account...${NC}"
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/storage.objectViewer"

# Create GCS bucket if it doesn't exist
echo -e "${YELLOW}Checking/creating GCS bucket...${NC}"
if ! gsutil ls -b gs://${GCS_BUCKET} &> /dev/null; then
    gsutil mb -p ${PROJECT_ID} -l ${LOCATION} gs://${GCS_BUCKET}
    echo -e "${GREEN}GCS bucket created.${NC}"
else
    echo -e "${GREEN}GCS bucket already exists.${NC}"
fi

# Grant bucket access to service account
echo -e "${YELLOW}Granting GCS bucket access...${NC}"
gsutil iam ch serviceAccount:${SERVICE_ACCOUNT}:roles/storage.objectViewer gs://${GCS_BUCKET}

# Create RAG corpus
echo -e "${YELLOW}Creating RAG corpus...${NC}"
CREATE_CORPUS_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d "{
        \"display_name\": \"${CORPUS_DISPLAY_NAME}\",
        \"description\": \"${CORPUS_DESCRIPTION}\"
    }" \
    "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/${LOCATION}/ragCorpora")

# Extract corpus ID from response
CORPUS_ID=$(echo ${CREATE_CORPUS_RESPONSE} | jq -r '.name' | awk -F'/' '{print $NF}')

if [ -z "${CORPUS_ID}" ] || [ "${CORPUS_ID}" = "null" ]; then
    echo -e "${RED}Error: Failed to create RAG corpus. Response: ${CREATE_CORPUS_RESPONSE}${NC}"
    exit 1
fi

echo -e "${GREEN}RAG corpus created with ID: ${CORPUS_ID}${NC}"

# Create sample directory structure in GCS (optional)
echo -e "${YELLOW}Creating sample directory structure in GCS...${NC}"
gsutil mkdir -p gs://${GCS_BUCKET}/documents/
gsutil mkdir -p gs://${GCS_BUCKET}/reports/
gsutil mkdir -p gs://${GCS_BUCKET}/analysis/

# Create configuration file
echo -e "${YELLOW}Creating configuration file...${NC}"
cat > rag-config.env << EOF
# RAG Engine Configuration
VERTEX_PROJECT=${PROJECT_ID}
VERTEX_LOCATION=${LOCATION}
RAG_CORPUS_ID=${CORPUS_ID}
GCS_BUCKET=${GCS_BUCKET}
SERVICE_ACCOUNT=${SERVICE_ACCOUNT}
EOF

echo -e "${GREEN}Configuration saved to rag-config.env${NC}"
echo -e "${GREEN}RAG Engine setup completed successfully!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Upload your documents to gs://${GCS_BUCKET}/documents/"
echo "2. Run the document ingestion script: ./scripts/ingest-documents.sh"
echo "3. Update your application environment variables with the values from rag-config.env"
