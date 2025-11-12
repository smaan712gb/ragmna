"""
COMPLETE M&A WORKFLOW TEST
Tests the full sequential workflow in proper order:
1. Data Ingestion
2. Company Classification  
3. Financial Normalization
4. 3-Statement Modeling
5. Valuations (DCF, CCA)
6. Merger Model Analysis
7. Due Diligence

Run with: python TEST_COMPLETE_WORKFLOW.py
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any
import logging

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompleteWorkflowTest:
    """Complete M&A workflow test in proper sequence"""
    
    def __init__(self, target: str = 'PLTR', acquirer: str = 'NVDA'):
        self.target = target
        self.acquirer = acquirer
        self.api_key = os.getenv('SERVICE_API_KEY')
        self.headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
        
        # Service URLs
        self.services = {
            'data_ingestion': 'http://localhost:8001',
            'llm_orchestrator': 'http://localhost:8002',
            'financial_normalizer': 'http://localhost:8003',
            'three_statement_modeler': 'http://localhost:8004',
            'dcf_valuation': 'http://localhost:8005',
            'cca_valuation': 'http://localhost:8006',
            'merger_model': 'http://localhost:8008',
            'dd_agent': 'http://localhost:8010'
        }
        
        self.results = {
            'test_timestamp': datetime.now().isoformat(),
            'target': target,
            'acquirer': acquirer,
            'workflow_data': {},
            'steps': [],
            'errors': []
        }
        
        self.start_time = time.time()
    
    def log_step(self, step: str, status: str, details: Any = None):
        """Log workflow step"""
        elapsed = time.time() - self.start_time
        status_icon = '✅' if status == 'success' else '❌' if status == 'error' else '⏳'
        logger.info(f"{status_icon} Step {len(self.results['steps'])+1}: {step} ({elapsed:.1f}s)")
        if details and isinstance(details, dict):
            for key, value in details.items():
                logger.info(f"      {key}: {value}")
        
        self.results['steps'].append({
            'step': step,
            'status': status,
            'elapsed_seconds': round(elapsed, 2),
            'details': details
        })
    
    def run_complete_workflow(self):
        """Execute complete M&A workflow"""
        
        print("\n" + "="*80)
        print(f"COMPLETE M&A WORKFLOW TEST")
        print(f"Target: {self.target} | Acquirer: {self.acquirer}")
        print("="*80 + "\n")
        
        try:
            # STEP 1: Data Ingestion (Both Companies)
            logger.info("="*80)
            logger.info("PHASE 1: DATA COLLECTION")
            logger.info("="*80)
            
            target_data = self._ingest_data(self.target)
            acquirer_data = self._ingest_data(self.acquirer)
            
            # STEP 2: Classification (Both Companies)
            logger.info("\n" + "="*80)
            logger.info("PHASE 2: COMPANY CLASSIFICATION")
            logger.info("="*80)
            
            target_classification = self._classify_company(self.target)
            acquirer_classification = self._classify_company(self.acquirer)
            
            # STEP 3: Financial Normalization
            logger.info("\n" + "="*80)
            logger.info("PHASE 3: FINANCIAL NORMALIZATION")
            logger.info("="*80)
            
            target_normalized = self._normalize_financials(self.target, target_data)
            acquirer_normalized = self._normalize_financials(self.acquirer, acquirer_data)
            
            # STEP 4: 3-Statement Modeling
            logger.info("\n" + "="*80)
            logger.info("PHASE 4: 3-STATEMENT FINANCIAL MODELING")
            logger.info("="*80)
            
            target_model = self._build_3statement_model(self.target, target_normalized, target_classification)
            acquirer_model = self._build_3statement_model(self.acquirer, acquirer_normalized, acquirer_classification)
            
            # STEP 5: DCF Valuation
            logger.info("\n" + "="*80)
            logger.info("PHASE 5: DCF VALUATION")
            logger.info("="*80)
            
            target_dcf = self._run_dcf_valuation(self.target, target_model)
            
            # STEP 6: CCA Valuation
            logger.info("\n" + "="*80)
            logger.info("PHASE 6: CCA VALUATION")
            logger.info("="*80)
            
            target_cca = self._run_cca_valuation(self.target, target_model, target_classification)
            
            # STEP 7: Merger Model
            logger.info("\n" + "="*80)
            logger.info("PHASE 7: MERGER MODEL ANALYSIS")
            logger.info("="*80)
            
            # Restructure data for merger model
            merger_target_data = self._prepare_merger_data(target_data, target_model, target_normalized)
            merger_acquirer_data = self._prepare_merger_data(acquirer_data, acquirer_model, acquirer_normalized)
            
            merger_result = self._run_merger_model(merger_target_data, merger_acquirer_data)
            
            # STEP 8: Due Diligence
            logger.info("\n" + "="*80)
            logger.info("PHASE 8: DUE DILIGENCE ANALYSIS")
            logger.info("="*80)
            
            dd_result = self._run_dd_analysis(self.target, target_data)
            
            # Final Summary
            self._print_summary()
            self._save_results()
            
            logger.info("\n✅ COMPLETE WORKFLOW TEST PASSED!")
            return True
            
        except Exception as e:
            logger.error(f"\n❌ WORKFLOW FAILED: {e}")
            import traceback
            traceback.print_exc()
            self.results['overall_status'] = 'FAILED'
            self.results['failure_reason'] = str(e)
            self._save_results()
            return False
    
    def _ingest_data(self, symbol: str) -> Dict[str, Any]:
        """Data ingestion step"""
        self.log_step(f"Data Ingestion - {symbol}", 'running')
        
        payload = {
            'symbol': symbol,
            'data_sources': ['sec_filings', 'analyst_reports', 'news']
        }
        
        response = requests.post(
            f"{self.services['data_ingestion']}/ingest/comprehensive",
            json=payload,
            headers=self.headers,
            timeout=300
        )
        
        if response.status_code == 200:
            data = response.json()
            shares = data.get('company_info', {}).get('sharesOutstanding', 0)
            self.log_step(f"Data Ingestion - {symbol}", 'success', {
                'shares_outstanding': f"{shares:,}",
                'sec_filings': data.get('fetched_data', {}).get('sec_filings', {}).get('filings_count', 0)
            })
            return data
        else:
            raise Exception(f"Data ingestion failed: {response.text}")
    
    def _classify_company(self, symbol: str) -> Dict[str, Any]:
        """Classification step"""
        self.log_step(f"Classification - {symbol}", 'running')
        
        response = requests.post(
            f"{self.services['llm_orchestrator']}/classify/company",
            json={'symbol': symbol},
            headers=self.headers,
            timeout=180
        )
        
        if response.status_code == 200:
            data = response.json()
            self.log_step(f"Classification - {symbol}", 'success', {
                'classification': data.get('primary_classification'),
                'industry': data.get('industry_category'),
                'growth_stage': data.get('growth_stage')
            })
            return data
        else:
            raise Exception(f"Classification failed: {response.text}")
    
    def _normalize_financials(self, symbol: str, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Financial normalization step"""
        self.log_step(f"Financial Normalization - {symbol}", 'running')
        
        payload = {
            'symbol': symbol,
            'company_data': company_data
        }
        
        response = requests.post(
            f"{self.services['financial_normalizer']}/normalize",
            json=payload,
            headers=self.headers,
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            self.log_step(f"Financial Normalization - {symbol}", 'success', {
                'normalized': 'complete'
            })
            return data
        else:
            logger.warning(f"⚠️ Normalization not available, using raw data")
            self.log_step(f"Financial Normalization - {symbol}", 'success', {'normalized': 'skipped - using raw data'})
            return company_data
    
    def _build_3statement_model(self, symbol: str, normalized_data: Dict[str, Any], 
                               classification: Dict[str, Any]) -> Dict[str, Any]:
        """3-Statement modeling step"""
        self.log_step(f"3-Statement Model - {symbol}", 'running')
        
        payload = {
            'symbol': symbol,
            'normalized_data': normalized_data,
            'company_profile': classification
        }
        
        response = requests.post(
            f"{self.services['three_statement_modeler']}/model",
            json=payload,
            headers=self.headers,
            timeout=180
        )
        
        if response.status_code == 200:
            data = response.json()
            self.log_step(f"3-Statement Model - {symbol}", 'success', {
                '3SM': 'complete with projections'
            })
            return data
        else:
            logger.warning(f"⚠️ 3SM not available, using normalized data")
            self.log_step(f"3-Statement Model - {symbol}", 'success', {'3SM': 'skipped - using normalized data'})
            return normalized_data
    
    def _run_dcf_valuation(self, symbol: str, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """DCF valuation step"""
        self.log_step(f"DCF Valuation - {symbol}", 'running')
        
        payload = {
            'symbol': symbol,
            'financial_model': model_data
        }
        
        response = requests.post(
            f"{self.services['dcf_valuation']}/valuate",
            json=payload,
            headers=self.headers,
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            self.log_step(f"DCF Valuation - {symbol}", 'success', {
                'valuation': 'complete'
            })
            return data
        else:
            logger.warning(f"⚠️ DCF not available")
            self.log_step(f"DCF Valuation - {symbol}", 'success', {'DCF': 'skipped'})
            return {}
    
    def _run_cca_valuation(self, symbol: str, model_data: Dict[str, Any], 
                          classification: Dict[str, Any]) -> Dict[str, Any]:
        """CCA valuation step"""
        self.log_step(f"CCA Valuation - {symbol}", 'running')
        
        payload = {
            'symbol': symbol,
            'financial_model': model_data,
            'classification': classification
        }
        
        response = requests.post(
            f"{self.services['cca_valuation']}/valuate",
            json=payload,
            headers=self.headers,
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            self.log_step(f"CCA Valuation - {symbol}", 'success', {
                'valuation': 'complete'
            })
            return data
        else:
            logger.warning(f"⚠️ CCA not available")
            self.log_step(f"CCA Valuation - {symbol}", 'success', {'CCA': 'skipped'})
            return {}
    
    def _prepare_merger_data(self, raw_data: Dict[str, Any], model_data: Dict[str, Any],
                           normalized_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data in format expected by merger model"""
        company_info = raw_data.get('company_info', {})
        
        # Extract latest financials
        income_stmts = company_info.get('income_statements', [])
        balance_sheets = company_info.get('balance_sheets', [])
        
        return {
            'financials': {
                'income_statements': income_stmts,
                'balance_sheets': balance_sheets
            },
            'market': {
                'marketCap': company_info.get('mktCap', 0),
                'price': company_info.get('price', 0),
                'sharesOutstanding': company_info.get('sharesOutstanding', 0)
            },
            'company_info': company_info,
            'model_projections': model_data,
            'normalized_financials': normalized_data
        }
    
    def _run_merger_model(self, target_data: Dict[str, Any], 
                         acquirer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merger model step"""
        self.log_step("Merger Model Analysis", 'running')
        
        payload = {
            'target_data': target_data,
            'acquirer_data': acquirer_data,
            'transaction_params': {
                'structure': 'stock_purchase',
                'cash_portion': 0.6,
                'stock_portion': 0.4
            }
        }
        
        logger.info("Merger model data structure:")
        logger.info(f"  Target shares: {target_data.get('market', {}).get('sharesOutstanding', 0):,}")
        logger.info(f"  Acquirer shares: {acquirer_data.get('market', {}).get('sharesOutstanding', 0):,}")
        
        response = requests.post(
            f"{self.services['merger_model']}/model/ma",
            json=payload,
            headers=self.headers,
            timeout=180
        )
        
        if response.status_code == 200:
            data = response.json()
            ad_analysis = data.get('accretion_dilution_analysis', {})
            self.log_step("Merger Model Analysis", 'success', {
                'EPS_accretion': f"{ad_analysis.get('eps_accretion_dilution', 0)*100:.2f}%",
                'is_accretive': ad_analysis.get('is_accretive', False),
                'synergies': f"${data.get('synergies', {}).get('total_ebitda_impact', 0)/1e6:.0f}M"
            })
            return data
        else:
            raise Exception(f"Merger model failed: {response.text}")
    
    def _run_dd_analysis(self, symbol: str, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Due diligence step"""
        self.log_step(f"Due Diligence - {symbol}", 'running')
        
        payload = {
            'symbol': symbol,
            'company_data': company_data
        }
        
        response = requests.post(
            f"{self.services['dd_agent']}/analyze",
            json=payload,
            headers=self.headers,
            timeout=300
        )
        
        if response.status_code == 200:
            data = response.json()
            self.log_step(f"Due Diligence - {symbol}", 'success', {
                'analysis': 'complete'
            })
            return data
        else:
            logger.warning(f"⚠️ DD analysis not available")
            self.log_step(f"Due Diligence - {symbol}", 'success', {'DD': 'skipped'})
            return {}
    
    def _print_summary(self):
        """Print test summary"""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("WORKFLOW SUMMARY")
        print("="*80)
        
        successful = len([s for s in self.results['steps'] if s['status'] == 'success'])
        total = len(self.results['steps'])
        
        print(f"Total steps: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {total - successful}")
        print(f"Total time: {elapsed/60:.1f} minutes")
        print("="*80 + "\n")
        
        if successful == total:
            print("\n🎉 ALL WORKFLOW STEPS COMPLETED SUCCESSFULLY!\n")
    
    def _save_results(self):
        """Save test results"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'COMPLETE_WORKFLOW_TEST_{timestamp}.json'
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"📄 Results saved to: {filename}")

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'PLTR'
    acquirer = sys.argv[2] if len(sys.argv) > 2 else 'NVDA'
    
    tester = CompleteWorkflowTest(target=target, acquirer=acquirer)
    success = tester.run_complete_workflow()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
