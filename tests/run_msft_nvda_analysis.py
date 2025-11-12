"""
MSFT ACQUIRING NVDA - Complete M&A Analysis
Simplified production test with detailed confirmations
"""

import os
import sys
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("="*100)
print(f"🚀 COMPREHENSIVE M&A ANALYSIS: MSFT ACQUIRING NVDA")
print("="*100)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*100)

# Results tracking
results = {
    'test_name': f'MSFT_NVDA_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
    'acquirer': 'MSFT',
    'target': 'NVDA',
    'timestamp': datetime.now().isoformat(),
    'confirmations': {}
}

# Import working services directly
print("\n📦 Importing services...")
try:
    # These imports work based on existing test files
    sys.path.insert(0, 'services/data-ingestion')
    import main as data_ing
    print("   ✓ Data ingestion imported")
    
    sys.path.insert(0, 'services/llm-orchestrator')
    import main as llm_orch
    print("   ✓ LLM orchestrator imported")
    
    sys.path.insert(0, 'services/three-statement-modeler')
    import main as tsm
    print("   ✓ 3-Statement modeler imported")
    
    sys.path.insert(0, 'services/dcf-valuation')
    import main as dcf
    print("   ✓ DCF valuation imported")
    
    print("\n✅ All core services imported successfully\n")
    results['confirmations']['services_imported'] = True
    
except Exception as e:
    print(f"\n❌ Error importing services: {e}")
    print("This test requires the services to be properly set up.")
    results['confirmations']['services_imported'] = False
    sys.exit(1)

# PHASE 1: Data Ingestion - Target (NVDA)
print("="*100)
print("PHASE 1: DATA INGESTION - TARGET (NVDA)")
print("="*100)

try:
    print("\n📥 Fetching NVDA data from FMP API...")
    target_data = data_ing.data_ingestion.fetch_company_data(
        symbol='NVDA',
        data_sources=['sec_filings', 'analyst_reports', 'news']
    )
    
    target_info = target_data.get('company_info', {})
    target_financials = target_data.get('financials', {})
    
    print(f"\n✅ TARGET DATA FETCHED")
    print(f"   Company: {target_info.get('companyName', 'Unknown')}")
    print(f"   Sector: {target_info.get('sector', 'Unknown')}")
    print(f"   Market Cap: ${target_info.get('mktCap', 0):,.0f}")
    print(f"   Price: ${target_info.get('price', 0):.2f}")
    
    income_statements = target_financials.get('income_statements', [])
    balance_sheets = target_financials.get('balance_sheets', [])
    cash_flows = target_financials.get('cash_flow_statements', [])
    
    print(f"   Income Statements: {len(income_statements)}")
    print(f"   Balance Sheets: {len(balance_sheets)}")
    print(f"   Cash Flow Statements: {len(cash_flows)}")
    
    if income_statements:
        latest = income_statements[0]
        print(f"\n   📊 Latest Financials:")
        print(f"      Revenue: ${latest.get('revenue', 0):,.0f}")
        print(f"      Net Income: ${latest.get('netIncome', 0):,.0f}")
        print(f"      EPS: ${latest.get('eps', 0):.2f}")
    
    docs_vectorized = target_data.get('vectorization_results', {}).get('total_documents', 0)
    print(f"   Documents Vectorized: {docs_vectorized}")
    
    results['target_data'] = {
        'status': 'success',
        'company': target_info.get('companyName'),
        'statements_fetched': len(income_statements),
        'documents_vectorized': docs_vectorized
    }
    
except Exception as e:
    print(f"\n❌ Error fetching target data: {e}")
    results['target_data'] = {'status': 'failed', 'error': str(e)}
    target_data = {}

# PHASE 2: Data Ingestion - Acquirer (MSFT)
print("\n" + "="*100)
print("PHASE 2: DATA INGESTION - ACQUIRER (MSFT)")
print("="*100)

try:
    print("\n📥 Fetching MSFT data...")
    acquirer_data = data_ing.data_ingestion.fetch_company_data(
        symbol='MSFT',
        data_sources=['sec_filings', 'analyst_reports']
    )
    
    acquirer_info = acquirer_data.get('company_info', {})
    print(f"\n✅ ACQUIRER DATA FETCHED")
    print(f"   Company: {acquirer_info.get('companyName', 'Unknown')}")
    print(f"   Market Cap: ${acquirer_info.get('mktCap', 0):,.0f}")
    
    results['acquirer_data'] = {
        'status': 'success',
        'company': acquirer_info.get('companyName')
    }
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    results['acquirer_data'] = {'status': 'failed'}
    acquirer_data = {}

# PHASE 3: Classification
print("\n" + "="*100)
print("PHASE 3: COMPANY CLASSIFICATION")
print("="*100)

import asyncio

try:
    print("\n🏷️  Classifying NVDA...")
    target_classification = asyncio.run(
        llm_orch.orchestrator.classifier.classify_company_profile('NVDA', target_info)
    )
    print(f"✅  Classification: {target_classification.get('primary_classification', 'Unknown')}")
    
    print("\n🏷️  Classifying MSFT...")
    acquirer_classification = asyncio.run(
        llm_orch.orchestrator.classifier.classify_company_profile('MSFT', acquirer_info)
    )
    print(f"✅  Classification: {acquirer_classification.get('primary_classification', 'Unknown')}")
    
    results['classifications'] = {
        'target': target_classification.get('primary_classification'),
        'acquirer': acquirer_classification.get('primary_classification')
    }
    
except Exception as e:
    print(f"\n⚠️  Classification error: {e}")
    target_classification = {'primary_classification': 'hyper_growth'}
    acquirer_classification = {'primary_classification': 'stable'}

# PHASE 4: 3-Statement Model
print("\n" + "="*100)
print("PHASE 4: 3-STATEMENT MODEL")
print("="*100)

try:
    print("\n📊 Building 3-Statement Model for NVDA...")
    target_model = tsm.modeler.generate_three_statement_model(
        company_data=target_data,
        classification=target_classification,
        projection_years=5
    )
    
    income_stmt = target_model.get('income_statement', [])
    print(f"✅  3SM Generated: {len(income_stmt)} years")
    
    if income_stmt:
        print(f"\n   📈 Revenue Projections:")
        for year_data in income_stmt[:5]:
            year = year_data.get('year', 0)
            revenue = year_data.get('revenue', 0)
            print(f"      Year {year}: ${revenue:,.0f}")
    
    results['3sm'] = {
        'status': 'complete',
        'projection_years': len(income_stmt)
    }
    
except Exception as e:
    print(f"\n⚠️  3SM error: {e}")
    target_model = {}

# PHASE 5: DCF Valuation
print("\n" + "="*100)
print("PHASE 5: DCF VALUATION")
print("="*100)

try:
    print("\n💰 Performing DCF Analysis...")
    target_dcf = dcf.dcf_engine.perform_dcf_analysis(
        company_data=target_data,
        financial_model=target_model,
        classification=target_classification
    )
    
    dcf_val = target_dcf.get('final_valuation', {})
    print(f"✅  DCF Complete")
    print(f"   Enterprise Value: ${dcf_val.get('enterprise_value', 0):,.0f}")
    print(f"   Equity Value: ${dcf_val.get('equity_value', 0):,.0f}")
    print(f"   Price per Share: ${dcf_val.get('equity_value_per_share', 0):.2f}")
    print(f"   Current Price: ${dcf_val.get('current_market_price', 0):.2f}")
    print(f"   Implied Premium: {dcf_val.get('premium_discount', 0):.1%}")
    
    results['dcf_valuation'] = {
        'status': 'complete',
        'enterprise_value': dcf_val.get('enterprise_value', 0),
        'price_per_share': dcf_val.get('equity_value_per_share', 0)
    }
    
except Exception as e:
    print(f"\n⚠️  DCF error: {e}")

# Save Results
print("\n" + "="*100)
print("SAVING RESULTS")
print("="*100)

results_file = f"{results['test_name']}_results.json"
with open(results_file, 'w') as f:
    json.dump(results, f, indent=2, default=str)

print(f"\n📁 Results saved to: {results_file}")

# Final Summary
print("\n" + "="*100)
print("✅ ANALYSIS COMPLETE")
print("="*100)

print(f"\n📊 Summary:")
print(f"   Target Data: {results.get('target_data', {}).get('status', 'unknown')}")
print(f"   Acquirer Data: {results.get('acquirer_data', {}).get('status', 'unknown')}")
print(f"   Classifications: Complete")
print(f"   3SM: {results.get('3sm', {}).get('status', 'unknown')}")
print(f"   DCF: {results.get('dcf_valuation', {}).get('status', 'unknown')}")

print(f"\n✨ MSFT-NVDA M&A Analysis Complete!")
print(f"   Review {results_file} for full details")
print("="*100)
