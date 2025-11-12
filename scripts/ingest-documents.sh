#!/bin/bash

# Document Ingestion Script for RAG Engine
# This script ingests documents from GCS into the RAG corpus

set -e

# Load configuration
if [ -f "rag-config.env" ]; then
    source rag-config.env
else
    echo "Error: rag-config.env not found. Please run setup-rag.sh first."
    exit 1
fi

# Configuration defaults (can be overridden by environment variables)
PROJECT_ID=${VERTEX_PROJECT}
LOCATION=${VERTEX_LOCATION}
CORPUS_ID=${RAG_CORPUS_ID}
GCS_BUCKET=${GCS_BUCKET}
GCS_PREFIX=${GCS_PREFIX:-"documents/"}  # Directory in GCS to ingest from
CHUNK_SIZE=${CHUNK_SIZE:-1000}  # Tokens per chunk
CHUNK_OVERLAP=${CHUNK_OVERLAP:-200}  # Overlap between chunks
EMBEDDING_QPM_RATE=${EMBEDDING_QPM_RATE:-1000}  # Embedding requests per minute

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting document ingestion into RAG corpus...${NC}"

# Validate configuration
if [ -z "${PROJECT_ID}" ] || [ -z "${LOCATION}" ] || [ -z "${CORPUS_ID}" ]; then
    echo -e "${RED}Error: Missing required configuration. Please check rag-config.env${NC}"
    exit 1
fi

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n 1 > /dev/null; then
    echo -e "${RED}Error: Not authenticated with gcloud. Please run 'gcloud auth login' first.${NC}"
    exit 1
fi

# Set project
gcloud config set project ${PROJECT_ID}

# Check if GCS bucket exists and has documents
echo -e "${YELLOW}Checking GCS bucket and documents...${NC}"
if ! gsutil ls gs://${GCS_BUCKET}/${GCS_PREFIX} > /dev/null 2>&1; then
    echo -e "${RED}Error: No documents found in gs://${GCS_BUCKET}/${GCS_PREFIX}${NC}"
    echo -e "${YELLOW}Please upload documents to your GCS bucket first.${NC}"
    exit 1
fi

# Count documents to be ingested
DOCUMENT_COUNT=$(gsutil ls gs://${GCS_BUCKET}/${GCS_PREFIX} | wc -l)
echo -e "${GREEN}Found ${DOCUMENT_COUNT} documents to ingest.${NC}"

# Prepare ingestion request
echo -e "${YELLOW}Starting document ingestion...${NC}"

INGEST_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d "{
        \"import_rag_files_config\": {
            \"gcs_source\": {
                \"uris\": [\"gs://${GCS_BUCKET}/${GCS_PREFIX}**\"]
            },
            \"rag_file_transformation_config\": {
                \"rag_file_chunking_config\": {
                    \"fixed_length_chunking\": {
                        \"chunk_size\": ${CHUNK_SIZE},
                        \"chunk_overlap\": ${CHUNK_OVERLAP}
                    }
                }
            },
            \"max_embedding_requests_per_min\": ${EMBEDDING_QPM_RATE}
        }
    }" \
    "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/${LOCATION}/ragCorpora/${CORPUS_ID}/ragFiles:import")

# Check if ingestion started successfully
if echo "${INGEST_RESPONSE}" | jq -e '.name' > /dev/null 2>&1; then
    OPERATION_NAME=$(echo ${INGEST_RESPONSE} | jq -r '.name')
    echo -e "${GREEN}Document ingestion started successfully!${NC}"
    echo -e "${YELLOW}Operation: ${OPERATION_NAME}${NC}"

    # Monitor the operation
    echo -e "${YELLOW}Monitoring ingestion progress...${NC}"

    while true; do
        OPERATION_STATUS=$(curl -s \
            -H "Authorization: Bearer $(gcloud auth print-access-token)" \
            "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/${OPERATION_NAME}")

        if echo "${OPERATION_STATUS}" | jq -e '.done' > /dev/null 2>&1; then
            if echo "${OPERATION_STATUS}" | jq -e '.response' > /dev/null 2>&1; then
                IMPORTED_COUNT=$(echo ${OPERATION_STATUS} | jq -r '.response.totalImportedRagFilesCount')
                echo -e "${GREEN}Ingestion completed successfully!${NC}"
                echo -e "${GREEN}Total files imported: ${IMPORTED_COUNT}${NC}"
            else
                ERROR_MESSAGE=$(echo ${OPERATION_STATUS} | jq -r '.error.message')
                echo -e "${RED}Ingestion failed: ${ERROR_MESSAGE}${NC}"
                exit 1
            fi
            break
        else
            # Show progress if available
            METADATA=$(echo ${OPERATION_STATUS} | jq -r '.metadata')
            if [ "${METADATA}" != "null" ]; then
                PROCESSED_COUNT=$(echo ${METADATA} | jq -r '.importedRagFilesCount // 0')
                echo -e "${YELLOW}Progress: ${PROCESSED_COUNT}/${DOCUMENT_COUNT} files processed...${NC}"
            fi
            sleep 10
        fi
    done

else
    ERROR_MESSAGE=$(echo ${INGEST_RESPONSE} | jq -r '.error.message // "Unknown error"')
    echo -e "${RED}Failed to start ingestion: ${ERROR_MESSAGE}${NC}"
    exit 1
fi

# Verify corpus has files
echo -e "${YELLOW}Verifying corpus contents...${NC}"
LIST_RESPONSE=$(curl -s \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/${LOCATION}/ragCorpora/${CORPUS_ID}/ragFiles")

FILE_COUNT=$(echo ${LIST_RESPONSE} | jq -r '.ragFiles | length')
echo -e "${GREEN}Corpus now contains ${FILE_COUNT} files.${NC}"

echo -e "${GREEN}Document ingestion completed successfully!${NC}"
echo -e "${YELLOW}Your RAG corpus is ready for queries.${NC}"
