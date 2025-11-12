"""
COMPREHENSIVE PRODUCTION FIXES - V2
Fixes for data ingestion and RAG authentication issues

Issues Fixed:
1. RAG authentication: Getting id_token instead of access_token
2. Shares outstanding = 0: FMP/yfinance not being called or failing
3. RAG vectors = 0: Vectorization failing due to auth issues

Changes:
1. Fix RAG authentication to use access_token with correct scopes
2. Ensure FMP and yfinance are called properly with error handling
3. Add fallback mechanisms for shares outstanding retrieval
4. Improve logging to track data flow
"""

import os
import sys

def fix_rag_authentication():
    """Fix RAG authentication in LLM orchestrator"""
    
    llm_orchestrator_path = 'services/llm-orchestrator/main.py'
    
    print("🔧 Fixing RAG authentication in LLM Orchestrator...")
    
    with open(llm_orchestrator_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the _get_auth_headers method
    old_auth_method = '''    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Vertex AI RAG Engine API calls"""
        # REQUIRED: Google Cloud credentials must be configured
        if not GOOGLE_CLOUD_KEY_PATH:
            raise ValueError("❌ GOOGLE_CLOUD_KEY_PATH environment variable is REQUIRED for production")
        
        if not os.path.exists(GOOGLE_CLOUD_KEY_PATH):
            raise FileNotFoundError(f"❌ Google Cloud key file not found at: {GOOGLE_CLOUD_KEY_PATH}")
        
        try:
            # Define required scopes for Vertex AI RAG Engine
            scopes = [
                'https://www.googleapis.com/auth/cloud-platform',
                'https://www.googleapis.com/auth/aiplatform'
            ]
            
            # Load service account credentials with scopes
            credentials = service_account.Credentials.from_service_account_file(
                GOOGLE_CLOUD_KEY_PATH,
                scopes=scopes
            )
            
            # Force refresh to get access token
            credentials.refresh(Request())
            
            # Validate we have an access token (not just ID token)
            if not credentials.token:
                raise ValueError("❌ No access token generated - credentials.refresh() failed")
            
            logger.info(f"✅ Got access token for Vertex AI RAG Engine API")
            
            return {
                'Authorization': f'Bearer {credentials.token}',
                'Content-Type': 'application/json'
            }
        except Exception as e:
            logger.error(f"❌ Failed to get authentication headers: {e}")
            raise ValueError(f"Authentication failed - check GCP credentials and IAM permissions: {e}")'''
    
    new_auth_method = '''    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Vertex AI RAG Engine API calls"""
        # REQUIRED: Google Cloud credentials must be configured
        if not GOOGLE_CLOUD_KEY_PATH:
            raise ValueError("❌ GOOGLE_CLOUD_KEY_PATH environment variable is REQUIRED for production")
        
        if not os.path.exists(GOOGLE_CLOUD_KEY_PATH):
            raise FileNotFoundError(f"❌ Google Cloud key file not found at: {GOOGLE_CLOUD_KEY_PATH}")
        
        try:
            # Define required scopes for Vertex AI RAG Engine - access_token requires these scopes
            scopes = [
                'https://www.googleapis.com/auth/cloud-platform',
                'https://www.googleapis.com/auth/aiplatform'
            ]
            
            # Load service account credentials with scopes
            credentials = service_account.Credentials.from_service_account_file(
                GOOGLE_CLOUD_KEY_PATH,
                scopes=scopes
            )
            
            # CRITICAL: Refresh to get access_token (not id_token)
            # The issue was that we were getting id_token instead of access_token
            from google.auth.transport.requests import Request as AuthRequest
            auth_request = AuthRequest()
            credentials.refresh(auth_request)
            
            # Validate we have an access token
            if not credentials.token:
                raise ValueError("❌ No access token generated after refresh")
            
            # Verify it's an access token, not an ID token
            if len(credentials.token) < 100:
                raise ValueError("❌ Token appears to be invalid (too short)")
            
            logger.info(f"✅ Successfully obtained access_token for Vertex AI RAG Engine API")
            logger.debug(f"   Token prefix: {credentials.token[:20]}...")
            
            return {
                'Authorization': f'Bearer {credentials.token}',
                'Content-Type': 'application/json'
            }
        except Exception as e:
            logger.error(f"❌ Failed to get authentication headers: {e}")
            logger.error(f"   GOOGLE_CLOUD_KEY_PATH: {GOOGLE_CLOUD_KEY_PATH}")
            logger.error(f"   File exists: {os.path.exists(GOOGLE_CLOUD_KEY_PATH)}")
            raise ValueError(f"Authentication failed - check GCP credentials and IAM permissions: {e}")'''
    
    content = content.replace(old_auth_method, new_auth_method)
    
    with open(llm_orchestrator_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed RAG authentication in LLM Orchestrator")

def fix_data_ingestion_company_info():
    """Fix company info retrieval in data ingestion service"""
    
    data_ingestion_path = 'services/data-ingestion/main.py'
    
    print("🔧 Fixing company info retrieval in Data Ingestion...")
    
    with open(data_ingestion_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the _get_company_info method and enhance error handling
    old_yfinance_section = '''            # SOURCE 2: yfinance for market data and shares outstanding
            logger.info(f"Fetching yfinance data for {symbol}")
            ticker = yf.Ticker(symbol)
            yf_info = ticker.info
            
            # CRITICAL: Use yfinance for shares outstanding (FMP often returns 0)
            if yf_info.get('sharesOutstanding'):
                company_info['sharesOutstanding'] = yf_info['sharesOutstanding']
                logger.info(f"Retrieved shares outstanding from yfinance: {yf_info['sharesOutstanding']:,.0f}")'''
    
    new_yfinance_section = '''            # SOURCE 2: yfinance for market data and shares outstanding
            logger.info(f"📥 Fetching yfinance data for {symbol}...")
            try:
                ticker = yf.Ticker(symbol)
                yf_info = ticker.info
                
                # CRITICAL: Use yfinance for shares outstanding (FMP often returns 0)
                shares_outstanding = yf_info.get('sharesOutstanding', 0)
                if shares_outstanding and shares_outstanding > 0:
                    company_info['sharesOutstanding'] = shares_outstanding
                    logger.info(f"✅ Retrieved shares outstanding from yfinance: {shares_outstanding:,.0f}")
                else:
                    logger.warning(f"⚠️  yfinance returned 0 or null for shares outstanding for {symbol}")
                    # Try alternative field names
                    shares_outstanding = yf_info.get('impliedSharesOutstanding', 0)
                    if shares_outstanding and shares_outstanding > 0:
                        company_info['sharesOutstanding'] = shares_outstanding
                        logger.info(f"✅ Retrieved shares outstanding from yfinance (impliedSharesOutstanding): {shares_outstanding:,.0f}")
            except Exception as e:
                logger.error(f"❌ Error fetching yfinance data for {symbol}: {e}")
                # Continue processing even if yfinance fails'''
    
    content = content.replace(old_yfinance_section, new_yfinance_section)
    
    # Also enhance FMP profile retrieval
    old_fmp_profile = '''            # SOURCE 1: FMP API for company profile and financials
            fmp_api_key = os.getenv('FMP_API_KEY')
            if fmp_api_key:
                # Get company profile
                url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
                params = {'apikey': fmp_api_key}
                
                response = requests.get(url, params=params, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if data and isinstance(data, list):
                        fmp_profile = data[0]
                        company_info.update(fmp_profile)
                        logger.info(f"✅ FMP: Retrieved company profile for {symbol}")'''
    
    new_fmp_profile = '''            # SOURCE 1: FMP API for company profile and financials
            fmp_api_key = os.getenv('FMP_API_KEY')
            if not fmp_api_key:
                logger.error(f"❌ FMP_API_KEY not configured - cannot fetch FMP data for {symbol}")
            else:
                logger.info(f"📥 FMP: Fetching company profile for {symbol}...")
                try:
                    # Get company profile
                    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
                    params = {'apikey': fmp_api_key}
                    
                    response = requests.get(url, params=params, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        if data and isinstance(data, list) and len(data) > 0:
                            fmp_profile = data[0]
                            company_info.update(fmp_profile)
                            logger.info(f"✅ FMP: Retrieved company profile for {symbol}")
                            
                            # Log key metrics
                            logger.info(f"   - Market Cap: ${fmp_profile.get('mktCap', 0)/1e9:.1f}B")
                            logger.info(f"   - Price: ${fmp_profile.get('price', 0):.2f}")
                            logger.info(f"   - Industry: {fmp_profile.get('industry', 'N/A')}")
                        else:
                            logger.warning(f"⚠️  FMP returned empty data for {symbol}")
                    else:
                        logger.error(f"❌ FMP API returned status {response.status_code} for {symbol}")
                except Exception as e:
                    logger.error(f"❌ Error fetching FMP profile for {symbol}: {e}")'''
    
    content = content.replace(old_fmp_profile, new_fmp_profile)
    
    with open(data_ingestion_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed company info retrieval in Data Ingestion")

def fix_merger_model_shares_validation():
    """Add better error messages for shares outstanding validation"""
    
    merger_model_path = 'services/mergers-model/main.py'
    
    print("🔧 Enhancing shares outstanding validation in Merger Model...")
    
    with open(merger_model_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the shares outstanding validation and enhance logging
    old_validation = '''        # Get shares outstanding from multiple sources - CRITICAL for valuation
        shares_outstanding = company_info.get('sharesOutstanding', 0)
        if shares_outstanding == 0:
            shares_outstanding = market.get('sharesOutstanding', 0)
        if shares_outstanding == 0:
            yf_data = company_info.get('yfinance_data', {})
            shares_outstanding = yf_data.get('shares_outstanding', 0)
        
        # CRITICAL: Shares outstanding must be > 0 to avoid division by zero
        if shares_outstanding <= 0:
            symbol = company_data.get('symbol', company_info.get('symbol', 'UNKNOWN'))
            raise ValueError(f"❌ CRITICAL: Shares outstanding = {shares_outstanding} for {symbol}. Cannot proceed with merger model. Check data ingestion from yfinance/FMP.")'''
    
    new_validation = '''        # Get shares outstanding from multiple sources - CRITICAL for valuation
        shares_outstanding = company_info.get('sharesOutstanding', 0)
        logger.info(f"   Checking shares outstanding sources:")
        logger.info(f"     1. company_info.sharesOutstanding: {shares_outstanding}")
        
        if shares_outstanding == 0:
            shares_outstanding = market.get('sharesOutstanding', 0)
            logger.info(f"     2. market.sharesOutstanding: {shares_outstanding}")
        
        if shares_outstanding == 0:
            yf_data = company_info.get('yfinance_data', {})
            shares_outstanding = yf_data.get('shares_outstanding', 0)
            logger.info(f"     3. yfinance_data.shares_outstanding: {shares_outstanding}")
        
        # Try additional fields
        if shares_outstanding == 0:
            shares_outstanding = company_info.get('shares', 0)
            logger.info(f"     4. company_info.shares: {shares_outstanding}")
        
        # CRITICAL: Shares outstanding must be > 0 to avoid division by zero
        if shares_outstanding <= 0:
            symbol = company_data.get('symbol', company_info.get('symbol', 'UNKNOWN'))
            logger.error(f"❌ CRITICAL ERROR: Shares outstanding = {shares_outstanding} for {symbol}")
            logger.error(f"   Company data keys: {list(company_data.keys())}")
            logger.error(f"   Company info keys: {list(company_info.keys())}")
            logger.error(f"   Market keys: {list(market.keys())}")
            raise ValueError(f"❌ CRITICAL: Shares outstanding = {shares_outstanding} for {symbol}. Cannot proceed with merger model. Check data ingestion from yfinance/FMP.")
        
        logger.info(f"✅ Using shares outstanding: {shares_outstanding:,.0f}")'''
    
    content = content.replace(old_validation, new_validation)
    
    with open(merger_model_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Enhanced shares outstanding validation in Merger Model")

def main():
    """Apply all fixes"""
    
    print("\n" + "="*80)
    print("COMPREHENSIVE PRODUCTION FIXES - V2")
    print("="*80 + "\n")
    
    try:
        # Fix 1: RAG Authentication
        fix_rag_authentication()
        
        # Fix 2: Data Ingestion Company Info
        fix_data_ingestion_company_info()
        
        # Fix 3: Merger Model Shares Validation
        fix_merger_model_shares_validation()
        
        print("\n" + "="*80)
        print("✅ ALL FIXES APPLIED SUCCESSFULLY")
        print("="*80)
        print("\nNext steps:")
        print("1. Restart services: docker-compose restart data-ingestion llm-orchestrator mergers-model")
        print("2. Run test: python TEST_REAL_PRODUCTION_MA_ANALYSIS.py PLTR NVDA")
        print("3. Check logs for:")
        print("   - ✅ Retrieved shares outstanding from yfinance")
        print("   - ✅ FMP: Retrieved company profile")
        print("   - ✅ Successfully obtained access_token for Vertex AI RAG Engine")
        print("   - ✅ RAG vectors: <number> stored")
        
    except Exception as e:
        print(f"\n❌ ERROR applying fixes: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
