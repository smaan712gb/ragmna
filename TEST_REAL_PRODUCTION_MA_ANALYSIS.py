"""
REAL PRODUCTION M&A ANALYSIS TEST
Tests complete end-to-end workflow with actual API calls and real data

This test:
1. Calls actual data-ingestion service (FMP, yfinance, SEC filings)
2. Calls LLM orchestrator for classification (Vertex AI RAG + Gemini)
3. Calls merger model service (validates shares outstanding)
4. Calls DD agent service for analysis
5. Validates all fixes are working in production

Run with: python TEST_REAL_PRODUCTION_MA_ANALYSIS.py
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RealProductionMATest:
    """Real production M&A analysis test with actual API calls"""
    
    def __init__(self, target: str = 'PLTR', acquirer: str = 'NVDA'):
        self.target = target
        self.acquirer = acquirer
        self.api_key = os.getenv('SERVICE_API_KEY', 'test-api-key-12345')
        self.headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
        
        # Service URLs
        self.data_ingestion_url = 'http://localhost:8001'
        self.llm_orchestrator_url = 'http://localhost:8002'
        self.merger_model_url = 'http://localhost:8008'
        self.dd_agent_url = 'http://localhost:8010'
        
        self.results = {
            'test_timestamp': datetime.now().isoformat(),
            'target': target,
            'acquirer': acquirer,
            'steps': [],
            'errors': []
        }
        
        self.start_time = time.time()
    
    def log_step(self, step: str, status: str, details: Any = None):
        """Log a test step"""
        elapsed = time.time() - self.start_time
        step_data = {
            'step': step,
            'status': status,
            'elapsed_seconds': round(elapsed, 2),
            'timestamp': datetime.now().isoformat()
        }
        if details:
            step_data['details'] = details
        
        self.results['steps'].append(step_data)
        
        status_icon = '✅' if status == 'success' else '❌' if status == 'error' else '⏳'
        logger.info(f"{status_icon} {step} ({elapsed:.1f}s)")
        if details and status == 'error':
            logger.error(f"   Error: {details}")
    
    def test_service_health(self, service_name: str, url: str) -> bool:
        """Test if service is healthy"""
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                self.log_step(f"Health check: {service_name}", 'success')
                return True
            else:
                self.log_step(f"Health check: {service_name}", 'error', f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_step(f"Health check: {service_name}", 'error', str(e))
            return False
    
    def test_data_ingestion(self, symbol: str) -> Dict[str, Any]:
        """Test real data ingestion with FMP, yfinance, SEC, news"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TESTING DATA INGESTION: {symbol}")
        logger.info(f"{'='*80}")
        
        try:
            self.log_step(f"Starting data ingestion for {symbol}", 'running')
            
            payload = {
                'symbol': symbol,
                'data_sources': ['sec_filings', 'analyst_reports', 'news']
            }
            
            print(f"   ⏳ Calling data ingestion API for {symbol}...")
            print(f"   ⏳ This may take 10-15 minutes with retry delays...")
            
            response = requests.post(
                f"{self.data_ingestion_url}/ingest/comprehensive",
                json=payload,
                headers=self.headers,
                timeout=900  # 15 minutes for comprehensive ingestion with retries
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate data structure
                assert 'company_info' in data, "Missing company_info"
                assert 'fetched_data' in data, "Missing fetched_data"
                assert 'vectorization_results' in data, "Missing vectorization_results"
                
                # Check yfinance shares outstanding
                shares = data.get('company_info', {}).get('sharesOutstanding', 0)
                yf_data = data.get('company_info', {}).get('yfinance_data', {})
                
                logger.info(f"  ✅ Company info retrieved")
                logger.info(f"     - Shares outstanding: {shares:,}" if shares > 0 else "     - ⚠️  Shares outstanding: 0 (THIS WILL CAUSE MERGER MODEL TO FAIL)")
                logger.info(f"     - Market cap: ${yf_data.get('market_cap', 0)/1e9:.1f}B" if yf_data.get('market_cap') else "     - Market cap: Not available")
                
                # Check SEC filings
                sec_filings = data.get('fetched_data', {}).get('sec_filings', {})
                filings_count = sec_filings.get('filings_count', 0)
                logger.info(f"  ✅ SEC filings: {filings_count} retrieved")
                
                # Check analyst reports
                analyst_reports = data.get('fetched_data', {}).get('analyst_reports', {})
                reports_count = analyst_reports.get('total_reports', 0)
                logger.info(f"  ✅ Analyst reports: {reports_count} retrieved")
                
                # Check news
                news = data.get('fetched_data', {}).get('news', {})
                news_count = news.get('total_items', 0)
                logger.info(f"  ✅ News articles: {news_count} retrieved")
                
                # Check vectorization
                vectorization = data.get('vectorization_results', {})
                vectors_stored = vectorization.get('vectors_stored', 0)
                logger.info(f"  ✅ RAG vectors: {vectors_stored} stored in Vertex AI RAG Engine")
                
                self.log_step(f"Data ingestion for {symbol}", 'success', {
                    'shares_outstanding': shares,
                    'sec_filings': filings_count,
                    'analyst_reports': reports_count,
                    'news': news_count,
                    'vectors_stored': vectors_stored
                })
                
                return data
            else:
                error_msg = f"Status {response.status_code}: {response.text}"
                self.log_step(f"Data ingestion for {symbol}", 'error', error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            self.log_step(f"Data ingestion for {symbol}", 'error', str(e))
            self.results['errors'].append(f"Data ingestion {symbol}: {str(e)}")
            raise
    
    def test_classification(self, symbol: str) -> Dict[str, Any]:
        """Test company classification with Vertex AI RAG + Gemini"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TESTING CLASSIFICATION: {symbol}")
        logger.info(f"{'='*80}")
        
        try:
            self.log_step(f"Starting classification for {symbol}", 'running')
            
            payload = {'symbol': symbol}
            
            print(f"   ⏳ Calling Gemini 2.5 Pro for classification...")
            
            response = requests.post(
                f"{self.llm_orchestrator_url}/classify/company",
                json=payload,
                headers=self.headers,
                timeout=180  # 3 minutes for AI classification
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate classification
                assert 'primary_classification' in data, "Missing primary_classification"
                assert 'industry_category' in data, "Missing industry_category"
                
                logger.info(f"  ✅ Classification complete")
                logger.info(f"     - Primary: {data.get('primary_classification')}")
                logger.info(f"     - Industry: {data.get('industry_category')}")
                logger.info(f"     - Growth stage: {data.get('growth_stage')}")
                logger.info(f"     - Risk profile: {data.get('risk_profile')}")
                
                self.log_step(f"Classification for {symbol}", 'success', {
                    'classification': data.get('primary_classification'),
                    'industry': data.get('industry_category')
                })
                
                return data
            else:
                error_msg = f"Status {response.status_code}: {response.text}"
                self.log_step(f"Classification for {symbol}", 'error', error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            self.log_step(f"Classification for {symbol}", 'error', str(e))
            self.results['errors'].append(f"Classification {symbol}: {str(e)}")
            raise
    
    def test_merger_model(self, target_data: Dict, acquirer_data: Dict) -> Dict[str, Any]:
        """Test merger model (validates shares outstanding)"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TESTING MERGER MODEL: {self.acquirer} → {self.target}")
        logger.info(f"{'='*80}")
        
        try:
            self.log_step("Starting merger model analysis", 'running')
            
            payload = {
                'target_data': target_data,
                'acquirer_data': acquirer_data,
                'transaction_params': {
                    'structure': 'stock_purchase',
                    'cash_portion': 0.6,
                    'stock_portion': 0.4
                }
            }
            
            print(f"   ⏳ Analyzing merger model...")
            
            response = requests.post(
                f"{self.merger_model_url}/model/ma",
                json=payload,
                headers=self.headers,
                timeout=180  # 3 minutes for merger calculations
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate merger model results
                assert 'accretion_dilution_analysis' in data, "Missing accretion_dilution_analysis"
                assert 'synergies' in data, "Missing synergies"
                
                accretion = data.get('accretion_dilution_analysis', {})
                synergies = data.get('synergies', {})
                
                logger.info(f"  ✅ Merger model complete")
                logger.info(f"     - Acquirer EPS: ${accretion.get('acquirer_eps', 0):.2f}")
                logger.info(f"     - Pro forma EPS: ${accretion.get('pro_forma_eps', 0):.2f}")
                logger.info(f"     - EPS accretion/dilution: {accretion.get('eps_accretion_dilution', 0)*100:.1f}%")
                logger.info(f"     - Is accretive: {accretion.get('is_accretive', False)}")
                logger.info(f"     - Total synergies: ${synergies.get('total_ebitda_impact', 0)/1e6:.0f}M")
                
                self.log_step("Merger model analysis", 'success', {
                    'eps_accretion': accretion.get('eps_accretion_dilution'),
                    'is_accretive': accretion.get('is_accretive'),
                    'synergies': synergies.get('total_ebitda_impact')
                })
                
                return data
            else:
                error_msg = f"Status {response.status_code}: {response.text}"
                self.log_step("Merger model analysis", 'error', error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            self.log_step("Merger model analysis", 'error', str(e))
            self.results['errors'].append(f"Merger model: {str(e)}")
            raise
    
    def test_dd_agent(self, symbol: str, company_data: Dict) -> Dict[str, Any]:
        """Test DD agent analysis"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TESTING DD AGENT: {symbol}")
        logger.info(f"{'='*80}")
        
        try:
            self.log_step(f"Starting DD analysis for {symbol}", 'running')
            
            payload = {
                'symbol': symbol,
                'company_data': company_data
            }
            
            print(f"   ⏳ Running DD agent analysis...")
            
            response = requests.post(
                f"{self.dd_agent_url}/analyze",
                json=payload,
                headers=self.headers,
                timeout=300  # 5 minutes for DD analysis
            )
            
            if response.status_code == 200:
                data = response.json()
                
                logger.info(f"  ✅ DD analysis complete")
                logger.info(f"     - Analysis generated")
                
                self.log_step(f"DD analysis for {symbol}", 'success')
                return data
            else:
                error_msg = f"Status {response.status_code}: {response.text}"
                self.log_step(f"DD analysis for {symbol}", 'error', error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            self.log_step(f"DD analysis for {symbol}", 'error', str(e))
            self.results['errors'].append(f"DD Agent {symbol}: {str(e)}")
            raise
    
    def run_complete_test(self):
        """Run complete production test"""
        
        print("\n" + "="*80)
        print(f"REAL PRODUCTION M&A ANALYSIS TEST")
        print(f"Target: {self.target} | Acquirer: {self.acquirer}")
        print("="*80 + "\n")
        
        try:
            # Test 1: Health checks
            logger.info("STEP 1: Service Health Checks")
            logger.info("-" * 80)
            services_healthy = True
            services_healthy &= self.test_service_health("Data Ingestion", self.data_ingestion_url)
            services_healthy &= self.test_service_health("LLM Orchestrator", self.llm_orchestrator_url)
            services_healthy &= self.test_service_health("Merger Model", self.merger_model_url)
            services_healthy &= self.test_service_health("DD Agent", self.dd_agent_url)
            
            if not services_healthy:
                raise Exception("⚠️  Some services are not healthy. Please start all services with 'docker-compose up -d'")
            
            # Test 2: Data Ingestion (Target)
            logger.info("\nSTEP 2: Data Ingestion - Target Company")
            logger.info("-" * 80)
            target_data = self.test_data_ingestion(self.target)
            
            # Test 3: Data Ingestion (Acquirer)
            logger.info("\nSTEP 3: Data Ingestion - Acquirer Company")
            logger.info("-" * 80)
            acquirer_data = self.test_data_ingestion(self.acquirer)
            
            # Test 4: Classification (Target)
            logger.info("\nSTEP 4: Classification - Target Company")
            logger.info("-" * 80)
            target_classification = self.test_classification(self.target)
            
            # Test 5: Classification (Acquirer)
            logger.info("\nSTEP 5: Classification - Acquirer Company")
            logger.info("-" * 80)
            acquirer_classification = self.test_classification(self.acquirer)
            
            # Test 6: Merger Model
            logger.info("\nSTEP 6: Merger Model Analysis")
            logger.info("-" * 80)
            merger_result = self.test_merger_model(target_data, acquirer_data)
            
            # Test 7: DD Agent
            logger.info("\nSTEP 7: Due Diligence Analysis")
            logger.info("-" * 80)
            dd_result = self.test_dd_agent(self.target, target_data)
            
            # Final Summary
            self.print_summary()
            self.save_results()
            
            return True
            
        except Exception as e:
            logger.error(f"\n❌ TEST FAILED: {e}")
            self.results['overall_status'] = 'FAILED'
            self.results['failure_reason'] = str(e)
            self.save_results()
            return False
    
    def print_summary(self):
        """Print test summary"""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        successful_steps = len([s for s in self.results['steps'] if s['status'] == 'success'])
        total_steps = len(self.results['steps'])
        
        print(f"Total steps: {total_steps}")
        print(f"Successful: {successful_steps}")
        print(f"Failed: {total_steps - successful_steps}")
        print(f"Total time: {elapsed:.1f} seconds")
        
        if self.results['errors']:
            print(f"\nErrors encountered:")
            for error in self.results['errors']:
                print(f"  - {error}")
        else:
            print("\n✅ ALL TESTS PASSED!")
        
        print("="*80 + "\n")
    
    def save_results(self):
        """Save test results"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'PRODUCTION_TEST_{self.target}_{self.acquirer}_{timestamp}.json'
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"📄 Test results saved to: {filename}")

def main():
    """Run production test"""
    
    # Parse arguments
    target = sys.argv[1] if len(sys.argv) > 1 else 'PLTR'
    acquirer = sys.argv[2] if len(sys.argv) > 2 else 'NVDA'
    
    # Check environment
    required_vars = ['SERVICE_API_KEY', 'FMP_API_KEY', 'VERTEX_PROJECT', 'RAG_CORPUS_ID', 'GCS_BUCKET']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing)}")
        logger.error("   Please configure your .env file")
        sys.exit(1)
    
    # Run test
    tester = RealProductionMATest(target=target, acquirer=acquirer)
    success = tester.run_complete_test()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
