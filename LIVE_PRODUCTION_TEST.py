"""
Live Production M&A Analysis Test
Direct service calls with RAG vectorization
NVDA acquires PLTR scenario
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
FMP_API_KEY = os.getenv('FMP_API_KEY')

# Service URLs (direct calls)
DATA_INGESTION_URL = "http://localhost:8001"
FINANCIAL_NORMALIZER_URL = "http://localhost:8003"
THREE_STATEMENT_URL = "http://localhost:8004"
DCF_URL = "http://localhost:8005"
CCA_URL = "http://localhost:8006"
LBO_URL = "http://localhost:8007"
MERGERS_URL = "http://localhost:8008"
DD_AGENT_URL = "http://localhost:8010"
BOARD_REPORTING_URL = "http://localhost:8011"

# Scenario
TARGET = "PLTR"
ACQUIRER = "NVDA"
PEERS = ["SNOW", "DDOG"]

def log(emoji, msg):
    print(f"{emoji} {msg}")

def log_sub(msg):
    print(f"   └─ {msg}")

def header(title):
    print("\n" + "="*100)
    print(f" {title}")
    print("="*100 + "\n")

def main():
    start_time = time.time()
    test_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {'test_id': test_id, 'steps': {}}
    
    print("\n" + "█"*100)
    print(f"█  🎯 LIVE PRODUCTION M&A ANALYSIS TEST".center(99) + "█")
    print(f"█  Scenario: {ACQUIRER} Acquires {TARGET}".center(99) + "█")
    print("█"*100 + "\n")
    
    # ========================================================================
    # PHASE 1: DATA INGESTION WITH RAG VECTORIZATION
    # ========================================================================
    header("PHASE 1: DATA INGESTION & RAG VECTORIZATION")
    
    headers = {'X-API-Key': SERVICE_API_KEY}
    
    # Ingest Target
    log("⏳", f"Ingesting {TARGET} (Target) - All sources with RAG...")
    try:
        r = requests.post(
            f"{DATA_INGESTION_URL}/ingest/comprehensive",
            json={'symbol': TARGET, 'data_sources': ['analyst_reports', 'news']},
            headers=headers,
            timeout=300
        )
        if r.status_code == 200:
            data = r.json()
            vec = data.get('vectorization_results', {})
            log("✅", f"{TARGET} ingested")
            log_sub(f"Vectors stored: {vec.get('vectors_stored', 0)}")
            log_sub(f"Documents: {vec.get('total_documents', 0)}")
            results['steps']['target_ingestion'] = {'success': True, 'vectors': vec.get('vectors_stored', 0)}
        else:
            log("❌", f"{TARGET} failed: {r.status_code}")
            results['steps']['target_ingestion'] = {'success': False}
    except Exception as e:
        log("❌", f"{TARGET} error: {str(e)[:100]}")
        results['steps']['target_ingestion'] = {'success': False, 'error': str(e)}
    
    time.sleep(2)
    
    # Ingest Acquirer
    log("⏳", f"Ingesting {ACQUIRER} (Acquirer)...")
    try:
        r = requests.post(
            f"{DATA_INGESTION_URL}/ingest/comprehensive",
            json={'symbol': ACQUIRER, 'data_sources': ['analyst_reports']},
            headers=headers,
            timeout=300
        )
        if r.status_code == 200:
            data = r.json()
            vec = data.get('vectorization_results', {})
            log("✅", f"{ACQUIRER} ingested")
            log_sub(f"Vectors stored: {vec.get('vectors_stored', 0)}")
            results['steps']['acquirer_ingestion'] = {'success': True, 'vectors': vec.get('vectors_stored', 0)}
        else:
            log("❌", f"{ACQUIRER} failed")
            results['steps']['acquirer_ingestion'] = {'success': False}
    except Exception as e:
        log("❌", f"{ACQUIRER} error: {str(e)[:100]}")
        results['steps']['acquirer_ingestion'] = {'success': False}
    
    time.sleep(2)
    
    # Ingest Peers
    for peer in PEERS:
        log("⏳", f"Ingesting {peer} (Peer)...")
        try:
            r = requests.post(
                f"{DATA_INGESTION_URL}/ingest/comprehensive",
                json={'symbol': peer, 'data_sources': ['analyst_reports']},
                headers=headers,
                timeout=300
            )
            if r.status_code == 200:
                data = r.json()
                vec = data.get('vectorization_results', {})
                log("✅", f"{peer} ingested")
                log_sub(f"Vectors: {vec.get('vectors_stored', 0)}")
                results['steps'][f'peer_{peer}'] = {'success': True, 'vectors': vec.get('vectors_stored', 0)}
            else:
                log("❌", f"{peer} failed")
                results['steps'][f'peer_{peer}'] = {'success': False}
        except Exception as e:
            log("❌", f"{peer} error")
            results['steps'][f'peer_{peer}'] = {'success': False}
        time.sleep(2)
    
    # ====================================================================================
    # PHASE 2: FINANCIAL NORMALIZATION
    # ====================================================================================
    header("PHASE 2: FINANCIAL NORMALIZATION")
    
    log("⏳", f"Normalizing {TARGET} financials...")
    try:
        r = requests.post(
            f"{FINANCIAL_NORMALIZER_URL}/normalize",
            json={'symbol': TARGET},
            headers=headers,
            timeout=120
        )
        if r.status_code == 200:
            data = r.json()
            log("✅", "Normalization complete")
            results['steps']['normalization'] = {'success': True}
        else:
            log("❌", f"Normalization failed: {r.status_code}")
            results['steps']['normalization'] = {'success': False}
    except Exception as e:
        log("❌", f"Normalization error: {str(e)[:100]}")
        results['steps']['normalization'] = {'success': False}
    
    # ========================================================================
    # PHASE 3: THREE-STATEMENT MODEL  
    # ========================================================================
    header("PHASE 3: THREE-STATEMENT MODEL")
    
    log("⏳", f"Building 3-statement model for {TARGET}...")
    try:
        r = requests.post(
            f"{THREE_STATEMENT_URL}/model",
            json={'symbol': TARGET, 'forecast_years': 5},
            headers=headers,
            timeout=120
        )
        if r.status_code == 200:
            data = r.json()
            log("✅", "3-statement model complete")
            results['steps']['three_statement'] = {'success': True}
        else:
            log("❌", f"3SM failed: {r.status_code}")
            results['steps']['three_statement'] = {'success': False}
    except Exception as e:
        log("❌", f"3SM error: {str(e)[:100]}")
        results['steps']['three_statement'] = {'success': False}
    
    # ========================================================================
    # PHASE 4: VALUATIONS
    # ========================================================================
    header("PHASE 4: VALUATION ANALYSIS")
    
    # DCF
    log("⏳", f"DCF Valuation for {TARGET}...")
    try:
        r = requests.post(
            f"{DCF_URL}/value",
            json={'symbol': TARGET, 'wacc': 10.0, 'terminal_growth_rate': 3.0},
            headers=headers,
            timeout=120
        )
        if r.status_code == 200:
            data = r.json()
            log("✅", "DCF complete")
            if 'valuation' in data:
                log_sub(f"Equity Value: ${data['valuation'].get('equity_value', 0)/1e9:.2f}B")
            results['steps']['dcf'] = {'success': True}
        else:
            log("❌", f"DCF failed: {r.status_code}")
            results['steps']['dcf'] = {'success': False}
    except Exception as e:
        log("❌", f"DCF error: {str(e)[:100]}")
        results['steps']['dcf'] = {'success': False}
    
    # CCA
    log("⏳", f"CCA for {TARGET}...")
    try:
        r = requests.post(
            f"{CCA_URL}/value",
            json={'symbol': TARGET, 'peer_companies': PEERS},
            headers=headers,
            timeout=120
        )
        if r.status_code == 200:
            data = r.json()
            log("✅", "CCA complete")
            results['steps']['cca'] = {'success': True}
        else:
            log("❌", f"CCA failed: {r.status_code}")
            results['steps']['cca'] = {'success': False}
    except Exception as e:
        log("❌", f"CCA error: {str(e)[:100]}")
        results['steps']['cca'] = {'success': False}
    
    # LBO
    log("⏳", f"LBO Analysis for {TARGET}...")
    try:
        r = requests.post(
            f"{LBO_URL}/analyze",
            json={'symbol': TARGET, 'entry_multiple': 12.0, 'exit_multiple': 11.0, 'debt_percentage': 60.0},
            headers=headers,
            timeout=120
        )
        if r.status_code == 200:
            data = r.json()
            log("✅", "LBO complete")
            if 'returns' in data:
                log_sub(f"IRR: {data['returns'].get('irr', 0)*100:.1f}%")
            results['steps']['lbo'] = {'success': True}
        else:
            log("❌", f"LBO failed: {r.status_code}")
            results['steps']['lbo'] = {'success': False}
    except Exception as e:
        log("❌", f"LBO error: {str(e)[:100]}")
        results['steps']['lbo'] = {'success': False}
    
    # ========================================================================
    # PHASE 5: MERGER MODEL
    # ========================================================================
    header("PHASE 5: MERGER MODEL")
    
    log("⏳", f"Merger Model: {ACQUIRER} acquires {TARGET}...")
    try:
        r = requests.post(
            f"{MERGERS_URL}/analyze",
            json={
                'acquirer_symbol': ACQUIRER,
                'target_symbol': TARGET,
                'deal_premium': 30.0,
                'synergy_rate': 0.15,
                'payment_type': 'cash_and_stock',
                'cash_percentage': 60.0
            },
            headers=headers,
            timeout=180
        )
        if r.status_code == 200:
            data = r.json()
            log("✅", "Merger Model complete")
            if 'analysis' in data:
                log_sub(f"Deal Value: ${data['analysis'].get('deal_value', 0)/1e9:.2f}B")
                log_sub(f"EPS Accretion: {data['analysis'].get('eps_accretion', 0)*100:.1f}%")
            results['steps']['merger_model'] = {'success': True}
        else:
            log("❌", f"Merger Model failed: {r.status_code}")
            results['steps']['merger_model'] = {'success': False}
    except Exception as e:
        log("❌", f"Merger Model error: {str(e)[:100]}")
        results['steps']['merger_model'] = {'success': False}
    
    # ========================================================================
    # PHASE 6: DUE DILIGENCE
    # ========================================================================
    header("PHASE 6: AI-POWERED DUE DILIGENCE")
    
    log("⏳", f"Due Diligence Agent for {TARGET}...")
    try:
        r = requests.post(
            f"{DD_AGENT_URL}/analyze",
            json={
                'target_symbol': TARGET,
                'acquirer_symbol': ACQUIRER,
                'focus_areas': ['financial', 'operational', 'strategic']
            },
            headers=headers,
            timeout=300
        )
        if r.status_code == 200:
            data = r.json()
            log("✅", "Due Diligence complete")
            results['steps']['dd'] = {'success': True}
        else:
            log("❌", f"DD failed: {r.status_code}")
            results['steps']['dd'] = {'success': False}
    except Exception as e:
        log("❌", f"DD error: {str(e)[:100]}")
        results['steps']['dd'] = {'success': False}
    
    # ========================================================================
    # PHASE 7: BOARD REPORTING
    # ========================================================================
    header("PHASE 7: BOARD-LEVEL REPORTING")
    
    log("⏳", f"Generating Board Report for {ACQUIRER}/{TARGET} transaction...")
    try:
        r = requests.post(
            f"{BOARD_REPORTING_URL}/generate",
            json={
                'acquirer_symbol': ACQUIRER,
                'target_symbol': TARGET,
                'analysis_type': 'complete_ma'
            },
            headers=headers,
            timeout=180
        )
        if r.status_code == 200:
            data = r.json()
            log("✅", "Board Report complete")
            results['steps']['board_report'] = {'success': True}
        else:
            log("❌", f"Board Report failed: {r.status_code}")
            results['steps']['board_report'] = {'success': False}
    except Exception as e:
        log("❌", f"Board Report error: {str(e)[:100]}")
        results['steps']['board_report'] = {'success': False}
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    elapsed = time.time() - start_time
    results['elapsed_seconds'] = elapsed
    results['end_time'] = datetime.now().isoformat()
    
    # Count successes
    successful = sum(1 for step in results['steps'].values() if step.get('success', False))
    total = len(results['steps'])
    
    header("🎯 TEST COMPLETE")
    log("📊", f"Duration: {elapsed/60:.1f} minutes")
    log("✅", f"Successful: {successful}/{total}")
    log("📁", f"Results: LIVE_PRODUCTION_TEST_{test_id}.json")
    
    # Save results
    with open(f"LIVE_PRODUCTION_TEST_{test_id}.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    # Final verdict
    if successful == total:
        print("\n" + "🎉"*50)
        print("🎉  ✅ FULL M&A PLATFORM IS LIVE! ✅".center(100) + "🎉")
        print("🎉"*50 + "\n")
        log("🚀", "Platform verified and ready for production use!")
    elif successful >= total * 0.7:
        log("⚠️", f"Platform mostly working ({successful}/{total} passed)")
        log("💡", "Review failed steps for optimization")
    else:
        log("❌", f"Multiple failures detected ({successful}/{total} passed)")
        log("🔍", "Check service logs for detailed errors")
    
    return results

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
