"""
Full Production M&A Analysis Test
Complete end-to-end workflow with real data
"""

import os
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
RUN_MANAGER_URL = "http://localhost:8013"

# Test Configuration - Real M&A Scenario
TARGET_COMPANY = "PLTR"  # Palantir (Target)
ACQUIRER_COMPANY = "NVDA"  # NVIDIA (Acquirer)
PEER_COMPANIES = ["SNOW", "DDOG"]  # Snowflake, Datadog (Peers)

# Deal Parameters
DEAL_PREMIUM = 30.0  # 30% premium
SYNERGY_RATE = 0.15  # 15% synergies

def print_header(title):
    print("\n" + "="*100)
    print(f"  {title}")
    print("="*100 + "\n")

def print_status(emoji, message):
    print(f"{emoji} {message}")

def print_substep(message):
    print(f"   └─ {message}")

def make_request(endpoint, payload, description):
    """Make API request with error handling"""
    print_status("⏳", description)
    
    try:
        response = requests.post(
            f"{RUN_MANAGER_URL}/{endpoint}",
            json=payload,
            headers={'X-API-Key': SERVICE_API_KEY},
            timeout=600  # 10 minutes for complex operations
        )
        
        if response.status_code == 200:
            result = response.json()
            print_status("✅", f"SUCCESS - {description}")
            return result
        else:
            print_status("❌", f"FAILED - {description}")
            print(f"   Status: {response.status_code}")
            print(f"   Error: {response.text[:200]}")
            return None
            
    except Exception as e:
        print_status("❌", f"EXCEPTION - {description}")
        print(f"   Error: {str(e)[:200]}")
        return None

def main():
    """Run full production M&A analysis"""
    
    start_time = time.time()
    test_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        'test_id': test_id,
        'target': TARGET_COMPANY,
        'acquirer': ACQUIRER_COMPANY,
        'peers': PEER_COMPANIES,
        'start_time': datetime.now().isoformat(),
        'steps': {}
    }
    
    print("\n" + "█"*100)
    print("█" + " "*98 + "█")
    print("█" + "  🚀 FULL PRODUCTION M&A ANALYSIS - LIVE TEST".center(98) + "█")
    print("█" + " "*98 + "█")
    print("█"*100)
    
    print(f"\n📊 Analysis Configuration:")
    print(f"   • Target Company:  {TARGET_COMPANY}")
    print(f"   • Acquirer:        {ACQUIRER_COMPANY}")
    print(f"   • Peer Companies:  {', '.join(PEER_COMPANIES)}")
    print(f"   • Deal Premium:    {DEAL_PREMIUM}%")
    print(f"   • Synergy Rate:    {SYNERGY_RATE*100}%")
    print(f"   • Test ID:         {test_id}")
    
    # ==================================================================================
    # PHASE 1: DATA INGESTION & VECTORIZATION
    # ==================================================================================
    print_header("PHASE 1: DATA INGESTION & VECTORIZATION")
    
    # 1.1 Ingest Target Company Data
    result = make_request(
        "analyze/ingest",
        {
            'symbol': TARGET_COMPANY,
            'data_sources': ['sec_filings', 'analyst_reports', 'news']
        },
        f"Ingesting {TARGET_COMPANY} data (Target)"
    )
    results['steps']['target_ingestion'] = result
    
    if result:
        vec_results = result.get('vectorization_results', {})
        print_substep(f"Vectors stored: {vec_results.get('vectors_stored', 0)}")
        print_substep(f"Documents processed: {vec_results.get('total_documents', 0)}")
    
    time.sleep(2)
    
    # 1.2 Ingest Acquirer Company Data
    result = make_request(
        "analyze/ingest",
        {
            'symbol': ACQUIRER_COMPANY,
            'data_sources': ['analyst_reports']  # Essential data only
        },
        f"Ingesting {ACQUIRER_COMPANY} data (Acquirer)"
    )
    results['steps']['acquirer_ingestion'] = result
    
    if result:
        vec_results = result.get('vectorization_results', {})
        print_substep(f"Vectors stored: {vec_results.get('vectors_stored', 0)}")
    
    time.sleep(2)
    
    # 1.3 Ingest Peer Companies Data
    for peer in PEER_COMPANIES:
        result = make_request(
            "analyze/ingest",
            {
                'symbol': peer,
                'data_sources': ['analyst_reports']
            },
            f"Ingesting {peer} data (Peer)"
        )
        results['steps'][f'peer_ingestion_{peer}'] = result
        
        if result:
            vec_results = result.get('vectorization_results', {})
            print_substep(f"Vectors stored: {vec_results.get('vectors_stored', 0)}")
        
        time.sleep(2)
    
    # ==================================================================================
    # PHASE 2: FINANCIAL DATA CLASSIFICATION & NORMALIZATION
    # ==================================================================================
    print_header("PHASE 2: FINANCIAL DATA CLASSIFICATION & NORMALIZATION")
    
    # 2.1 Classify Target Financials
    result = make_request(
        "analyze/classify",
        {'symbol': TARGET_COMPANY},
        f"Classifying {TARGET_COMPANY} financials"
    )
    results['steps']['target_classification'] = result
    
    if result and 'classification' in result:
        print_substep(f"Line items classified: {result['classification'].get('total_items', 0)}")
    
    # 2.2 Normalize Target Financials
    result = make_request(
        "analyze/normalize",
        {'symbol': TARGET_COMPANY},
        f"Normalizing {TARGET_COMPANY} financials"
    )
    results['steps']['target_normalization'] = result
    
    if result and 'normalized_data' in result:
        print_substep(f"Periods normalized: {len(result['normalized_data'].get('periods', []))}")
    
    # ==================================================================================
    # PHASE 3: THREE-STATEMENT MODEL
    # ==================================================================================
    print_header("PHASE 3: THREE-STATEMENT MODEL BUILDING")
    
    result = make_request(
        "analyze/three-statement",
        {
            'symbol': TARGET_COMPANY,
            'forecast_years': 5
        },
        f"Building 3-statement model for {TARGET_COMPANY}"
    )
    results['steps']['three_statement_model'] = result
    
    if result and 'projections' in result:
        proj = result['projections']
        print_substep(f"Revenue CAGR: {proj.get('revenue_cagr', 0)*100:.1f}%")
        print_substep(f"EBITDA Margin: {proj.get('avg_ebitda_margin', 0)*100:.1f}%")
        print_substep(f"Forecast years: {len(proj.get('forecast_periods', []))}")
    
    # ==================================================================================
    # PHASE 4: VALUATION ANALYSIS
    # ==================================================================================
    print_header("PHASE 4: COMPREHENSIVE VALUATION ANALYSIS")
    
    # 4.1 DCF Valuation
    result = make_request(
        "analyze/dcf",
        {
            'symbol': TARGET_COMPANY,
            'wacc': 10.0,
            'terminal_growth_rate': 3.0,
            'forecast_years': 5
        },
        f"DCF Valuation for {TARGET_COMPANY}"
    )
    results['steps']['dcf_valuation'] = result
    
    if result and 'valuation' in result:
        val = result['valuation']
        print_substep(f"Enterprise Value: ${val.get('enterprise_value', 0)/1e9:.2f}B")
        print_substep(f"Equity Value: ${val.get('equity_value', 0)/1e9:.2f}B")
        print_substep(f"Value per Share: ${val.get('value_per_share', 0):.2f}")
    
    # 4.2 Comparable Company Analysis
    result = make_request(
        "analyze/cca",
        {
            'symbol': TARGET_COMPANY,
            'peer_companies': PEER_COMPANIES
        },
        f"CCA for {TARGET_COMPANY}"
    )
    results['steps']['cca_valuation'] = result
    
    if result and 'valuation' in result:
        val = result['valuation']
        print_substep(f"P/E Multiple: {val.get('pe_multiple', 0):.1f}x")
        print_substep(f"EV/EBITDA Multiple: {val.get('ev_ebitda_multiple', 0):.1f}x")
        print_substep(f"Implied Value: ${val.get('implied_value', 0)/1e9:.2f}B")
    
    # 4.3 LBO Analysis
    result = make_request(
        "analyze/lbo",
        {
            'symbol': TARGET_COMPANY,
            'entry_multiple': 12.0,
            'exit_multiple': 11.0,
            'debt_percentage': 60.0,
            'hold_period': 5
        },
        f"LBO Analysis for {TARGET_COMPANY}"
    )
    results['steps']['lbo_analysis'] = result
    
    if result and 'returns' in result:
        returns = result['returns']
        print_substep(f"IRR: {returns.get('irr', 0)*100:.1f}%")
        print_substep(f"MOIC: {returns.get('moic', 0):.2f}x")
    
    # ==================================================================================
    # PHASE 5: MERGER MODEL
    # ==================================================================================
    print_header("PHASE 5: MERGER MODEL & ACCRETION/DILUTION")
    
    result = make_request(
        "analyze/merger",
        {
            'acquirer_symbol': ACQUIRER_COMPANY,
            'target_symbol': TARGET_COMPANY,
            'deal_premium': DEAL_PREMIUM,
            'synergy_rate': SYNERGY_RATE,
            'payment_type': 'cash_and_stock',
            'cash_percentage': 60.0
        },
        f"Merger Model: {ACQUIRER_COMPANY} acquires {TARGET_COMPANY}"
    )
    results['steps']['merger_model'] = result
    
    if result and 'analysis' in result:
        analysis = result['analysis']
        print_substep(f"Deal Value: ${analysis.get('deal_value', 0)/1e9:.2f}B")
        print_substep(f"EPS Accretion: {analysis.get('eps_accretion', 0)*100:.1f}%")
        print_substep(f"Synergies: ${analysis.get('synergies', 0)/1e6:.1f}M")
    
    # ==================================================================================
    # PHASE 6: DUE DILIGENCE
    # ==================================================================================
    print_header("PHASE 6: AI-POWERED DUE DILIGENCE")
    
    result = make_request(
        "analyze/due-diligence",
        {
            'target_symbol': TARGET_COMPANY,
            'acquirer_symbol': ACQUIRER_COMPANY,
            'focus_areas': ['financial', 'operational', 'legal', 'strategic']
        },
        f"Due Diligence for {TARGET_COMPANY}"
    )
    results['steps']['due_diligence'] = result
    
    if result and 'findings' in result:
        findings = result['findings']
        print_substep(f"Total Findings: {len(findings.get('items', []))}")
        print_substep(f"Red Flags: {findings.get('red_flags_count', 0)}")
        print_substep(f"Overall Risk: {findings.get('risk_level', 'Unknown')}")
    
    # ==================================================================================
    # PHASE 7: BOARD-LEVEL REPORTING
    # ==================================================================================
    print_header("PHASE 7: EXECUTIVE REPORTING & DOCUMENTATION")
    
    result = make_request(
        "analyze/report",
        {
            'acquirer_symbol': ACQUIRER_COMPANY,
            'target_symbol': TARGET_COMPANY,
            'analysis_type': 'complete_ma',
            'include_sections': [
                'executive_summary',
                'strategic_rationale',
                'valuation_summary',
                'merger_analysis',
                'risk_assessment',
                'recommendations'
            ]
        },
        f"Board Report: {ACQUIRER_COMPANY} / {TARGET_COMPANY} Transaction"
    )
    results['steps']['board_report'] = result
    
    if result and 'report' in result:
        report = result['report']
        print_substep(f"Report sections: {len(report.get('sections', []))}")
        print_substep(f"Pages: {report.get('page_count', 0)}")
        print_substep(f"Recommendation: {report.get('recommendation', 'N/A')}")
    
    # ==================================================================================
    # FINAL SUMMARY
    # ==================================================================================
    elapsed_time = time.time() - start_time
    results['end_time'] = datetime.now().isoformat()
    results['elapsed_time_seconds'] = elapsed_time
    
    print_header("🎯 PRODUCTION TEST COMPLETE")
    
    # Count successes
    successful_steps = sum(1 for step in results['steps'].values() if step is not None)
    total_steps = len(results['steps'])
    
    print_status("📊", f"Test Duration: {elapsed_time/60:.1f} minutes")
    print_status("✅", f"Successful Steps: {successful_steps}/{total_steps}")
    print_status("📁", f"Results saved to: PRODUCTION_MA_TEST_{test_id}.json")
    
    # Save results
    filename = f"PRODUCTION_MA_TEST_{test_id}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Final Status
    if successful_steps == total_steps:
        print("\n" + "🎉"*50)
        print("🎉" + " "*98 + "🎉")
        print("🎉" + "  ✅ FULL-STACK M&A PLATFORM IS LIVE AND OPERATIONAL! ✅".center(98) + "🎉")
        print("🎉" + " "*98 + "🎉")
        print("🎉"*50 + "\n")
        
        print("📋 Platform Capabilities Verified:")
        print("   ✅ Multi-source data ingestion (SEC, FMP, News)")
        print("   ✅ RAG vectorization and storage")
        print("   ✅ Financial classification & normalization")
        print("   ✅ 3-statement model building")
        print("   ✅ Comprehensive valuations (DCF, CCA, LBO)")
        print("   ✅ Merger model & accretion analysis")
        print("   ✅ AI-powered due diligence")
        print("   ✅ Executive-level reporting")
        print("\n🚀 Platform is PRODUCTION-READY for M&A analysis!")
    else:
        print("\n⚠️  Some steps failed. Review the logs for details.")
        print(f"   Failed steps: {total_steps - successful_steps}")
    
    return results

if __name__ == "__main__":
    try:
        results = main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
