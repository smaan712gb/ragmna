# DD Agent Production Deployment Guide

## Overview
This guide provides complete steps to deploy the DD Agent with full service integration and real data processing.

## Current Status

### ✅ Completed
1. **Requirements Files Created**
   - `services/dcf-valuation/requirements.txt`
   - `services/cca-valuation/requirements.txt`
   - `services/lbo-analysis/requirements.txt`
   - `services/three-statement-modeler/requirements.txt`
   - `services/data-ingestion/requirements.txt` (fixed with compatible versions)

2. **Docker Images**
   - `data-ingestion`: ✅ Built successfully

3. **Production-Ready DD Agent**
   - `services/dd-agent/main_production.py`: Enhanced error handling version
   - `TEST_DD_AGENT_PRODUCTION.py`: Comprehensive production test suite

### ⚠️ Remaining Work for Full Production

## Step 1: Build All Docker Services

```powershell
# Build all remaining services
docker-compose build three-statement-modeler dcf-valuation cca-valuation lbo-analysis
```

## Step 2: Start All Services

```powershell
# Start all services
docker-compose up -d data-ingestion three-statement-modeler dcf-valuation cca-valuation lbo-analysis dd-agent

# Verify all services are running
docker-compose ps
```

## Step 3: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Service API Key
SERVICE_API_KEY=your-secure-api-key-here

# FMP API Key (for real financial data)
FMP_API_KEY=your-fmp-api-key-here

# Gemini API Key (for LLM operations)
GEMINI_API_KEY=your-gemini-api-key-here

# Google Cloud Configuration (for RAG)
VERTEX_PROJECT=your-gcp-project-id
VERTEX_LOCATION=us-central1
RAG_CORPUS_ID=your-rag-corpus-id
GOOGLE_CLOUD_KEY_PATH=/path/to/service-account-key.json
```

## Step 4: Run Integration Test

```powershell
# Activate conda environment
conda activate ragmna

# Run the DD Agent test against port 8010 (Docker version)
# Edit TEST_DD_AGENT_COMPREHENSIVE.py to use port 8010
python TEST_DD_AGENT_COMPREHENSIVE.py
```

## Step 5: Verify Full Data Pipeline

The complete data flow should be:

```
1. Data Ingestion (Port 8001)
   ├── Fetches company data from FMP API
   ├── Stores vectors
   └── Provides to downstream services

2. Financial Normalizer (Port 8003)
   └── Classifies company (hyper_growth, growth, etc.)

3. Three-Statement Modeler (Port 8004)
   └── Builds financial projections

4. Valuation Services
   ├── DCF Valuation (Port 8005)
   ├── CCA Valuation (Port 8006)
   └── LBO Analysis (Port 8007)

5. DD Agent (Port 8010)
   ├── Integrates all vectors
   ├── Performs comprehensive risk analysis
   ├── Uses RAG for document insights
   └── Generates recommendations
```

## Expected Test Results (Production Mode)

When all services are running with real data:

```
✅ Vector Sources:
  - Ingestion vectors available: TRUE
  - Financial models available: TRUE
  - RAG vectors available: TRUE (if RAG configured)
  
✅ Risk Analysis:
  - All 5 categories with RAG insights
  - Real financial model integration
  - Document analysis with actual SEC filings

✅ Validation Checks:
  ✓ Ingestion Vectors
  ✓ Financial Models  
  ✓ RAG Vectors
  ✓ RAG Contexts Retrieved
  ✓ All Risk Categories
  ✓ RAG Insights Present
  ✓ Financial Model Analysis
  ✓ Document Analysis Complete
  ✓ Comprehensive DD Flag
```

## Service Ports Reference

| Service | Port | Purpose |
|---------|------|---------|
| data-ingestion | 8001 | Fetch & store company data |
| llm-orchestrator | 8002 | LLM operations |
| financial-normalizer | 8003 | Classify companies |
| three-statement-modeler | 8004 | Build 3-statement model |
| dcf-valuation | 8005 | DCF analysis |
| cca-valuation | 8006 | Comparable company analysis |
| lbo-analysis | 8007 | LBO analysis |
| mergers-model | 8008 | M&A modeling |
| precedent-transactions | 8009 | Precedent transactions |
| dd-agent | 8010 | Due diligence analysis |
| board-reporting | 8011 | Board reports |
| excel-exporter | 8012 | Excel export |
| run-manager | 8013 | Orchestration |
| qa-engine | 8014 | QA checks |

## Production Checklist

### Infrastructure
- [ ] Docker Desktop running
- [ ] All services built
- [ ] All services started and healthy
- [ ] Environment variables configured

### Data Sources
- [ ] FMP API key configured
- [ ] Real company data being fetched
- [ ] Financial data normalized
- [ ] Projections calculated

### RAG Integration (Optional but Recommended)
- [ ] Vertex AI RAG corpus created
- [ ] Documents ingested to RAG
- [ ] RAG_CORPUS_ID configured
- [ ] Service account credentials configured

### Testing
- [ ] Health checks passing for all services
- [ ] Data ingestion works with real symbols
- [ ] Financial models calculate correctly
- [ ] DD Agent receives all vectors
- [ ] Comprehensive analysis completes
- [ ] All validation checks pass

## Troubleshooting

### Services Not Starting
```powershell
# Check logs
docker-compose logs [service-name]

# Restart specific service
docker-compose restart [service-name]
```

### Missing Dependencies
```powershell
# Rebuild specific service
docker-compose build --no-cache [service-name]
```

### Network Issues
```powershell
# Recreate network
docker-compose down
docker network prune
docker-compose up -d
```

## Performance Optimization

### For Production Use:
1. **Increase Resource Limits** in docker-compose.yml
2. **Enable Caching** for frequent queries
3. **Use Production WSGI Server** (Gunicorn) instead of Flask dev server
4. **Implement Rate Limiting** for API calls
5. **Add Monitoring** with Prometheus/Grafana

## Next Steps

1. **Complete Service Deployment**
   ```powershell
   docker-compose build
   docker-compose up -d
   ```

2. **Run Full Integration Test**
   ```powershell
   conda activate ragmna
   python TEST_DD_AGENT_COMPREHENSIVE.py
   ```

3. **Verify All Validation Checks Pass**
   - Check that all 9 validation checks show ✓
   - Ensure RAG insights are present in all categories
   - Confirm financial models are integrated

4. **Production Hardening**
   - Replace dev secrets with secure vault
   - Enable HTTPS/TLS
   - Add authentication/authorization
   - Implement logging and monitoring
   - Set up CI/CD pipeline

## Success Criteria

The system is production-ready when:

1. ✅ All 15 microservices are running
2. ✅ Real data flows through entire pipeline
3. ✅ All 9 validation checks pass
4. ✅ < 30 second end-to-end analysis time
5. ✅ RAG provides meaningful insights
6. ✅ Financial models integrate correctly
7. ✅ Zero fallbacks in production mode
8. ✅ Comprehensive due diligence completed

## Contact & Support

For issues or questions:
- Check service logs: `docker-compose logs -f [service]`
- Review test outputs in JSON files
- Verify environment variables are set
- Ensure all APIs have valid keys

---

**Last Updated**: November 11, 2025
**Version**: 1.0.0
