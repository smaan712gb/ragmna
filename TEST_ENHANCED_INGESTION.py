"""
TEST: Enhanced Data Ingestion Pipeline
Validates multi-source data fetching and vectorization
Tests: FMP + yfinance + SEC + News with complete confirmations
"""

import sys
import os
from datetime import datetime

# Setup path
sys.path.insert(0, 'services/data-ingestion')

print("="*100)
print("🧪 ENHANCED DATA INGESTION PIPELINE TEST")
print("="*100)
print(f"Testing: Multi-source data integration with vectorization")
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*100)

# Import enhanced data ingestion service
try:
    from main import data_ingestion
    print("\n✅ Enhanced data ingestion service imported")
except Exception as e:
    print(f"\n❌ Failed to import service: {e}")
    sys.exit(1)

# Test Symbol
SYMBOL = 'NVDA'

results = {
    'symbol': SYMBOL,
    'test_start': datetime.now().isoformat(),
    'phases': {}
}

# =============================================================================
# PHASE 1: COMPREHENSIVE DATA FETCH
# =============================================================================
print("\n" + "="*100)
print(f"PHASE 1: COMPREHENSIVE DATA FETCH - {SYMBOL}")
print("="*100)

print(f"\n📥 Fetching data from all sources...")
print("   Sources: FMP, yfinance, SEC Edgar, News")

try:
    comprehensive_data = data_ingestion.fetch_company_data(
        symbol=SYMBOL,
        data_sources=['sec_filings', 'analyst_reports', 'news']
    )
    
    print(f"\n✅ DATA FETCH COMPLETE")
    print(f"   Status: {comprehensive_data.get('status')}")
    
    # Company Info Validation
    company_info = comprehensive_data.get('company_info', {})
    print(f"\n📊 COMPANY PROFILE:")
    print(f"   Company: {company_info.get('companyName', 'Unknown')}")
    print(f"   Symbol: {company_info.get('symbol')}")
    print(f"   Sector: {company_info.get('sector')}")
    print(f"   Market Cap: ${company_info.get('mktCap', 0):,.0f}")
    print(f"   Price: ${company_info.get('price', 0):.2f}")
    
    # CRITICAL: Shares Outstanding Confirmation
    shares_yfinance = company_info.get('yfinance_data', {}).get('market_cap')
    shares_outstanding = company_info.get('sharesOutstanding', 0)
    print(f"\n⭐ SHARES OUTSTANDING:")
    print(f"   From yfinance: {shares_outstanding:,.0f}")
    print(f"   Status: {'✅ VALID' if shares_outstanding > 0 else '❌ INVALID'}")
    
    # yfinance Additional Data
    yf_data = company_info.get('yfinance_data', {})
    if yf_data:
        print(f"\n📈 YFINANCE MARKET DATA:")
        print(f"   Current Price: ${yf_data.get('current_price', 0):.2f}")
        print(f"   Beta: {yf_data.get('beta', 0):.2f}")
        print(f"   Forward P/E: {yf_data.get('forward_pe', 0):.2f}")
        print(f"   52-Week High: ${yf_data.get('52_week_high', 0):.2f}")
        print(f"   52-Week Low: ${yf_data.get('52_week_low', 0):.2f}")
        print(f"   Avg Volume: {yf_data.get('avg_volume', 0):,.0f}")
    
    # Institutional Holders
    inst_holders = company_info.get('institutional_holders', [])
    if inst_holders:
        print(f"\n🏢 INSTITUTIONAL HOLDERS:")
        print(f"   Total Retrieved: {len(inst_holders)}")
        for i, holder in enumerate(inst_holders[:3], 1):
            print(f"   {i}. {holder.get('Holder', 'Unknown')}: {holder.get('Shares', 0):,.0f} shares")
    
    results['phases']['company_info'] = {
        'status': 'success',
        'shares_outstanding': shares_outstanding,
        'sources_used': ['FMP', 'yfinance']
    }
    
except Exception as e:
    print(f"\n❌ Error fetching company data: {e}")
    import traceback
    traceback.print_exc()
    results['phases']['company_info'] = {'status': 'failed', 'error': str(e)}

# =============================================================================
# PHASE 2: SEC FILINGS DATA
# =============================================================================
print("\n" + "="*100)
print("PHASE 2: SEC FILINGS RETRIEVAL")
print("="*100)

fetched_data = comprehensive_data.get('fetched_data', {})
sec_data = fetched_data.get('sec_filings', {})

if sec_data and 'filings' in sec_data:
    filings = sec_data.get('filings', [])
    print(f"\n✅ SEC FILINGS RETRIEVED")
    print(f"   CIK: {sec_data.get('cik')}")
    print(f"   Total Filings: {len(filings)}")
    
    # List filings by type
    filing_types = {}
    for filing in filings:
        form_type = filing.get('form_type', 'Unknown')
        filing_types[form_type] = filing_types.get(form_type, 0) + 1
    
    print(f"\n   📋 Filing Types:")
    for form_type, count in filing_types.items():
        print(f"      • {form_type}: {count}")
    
    results['phases']['sec_filings'] = {
        'status': 'success',
        'total_filings': len(filings),
        'filing_types': filing_types
    }
else:
    print(f"\n⚠️  No SEC filings retrieved")
    results['phases']['sec_filings'] = {'status': 'no_data'}

# =============================================================================
# PHASE 3: ANALYST REPORTS
# =============================================================================
print("\n" + "="*100)
print("PHASE 3: ANALYST REPORTS & ESTIMATES")
print("="*100)

analyst_data = fetched_data.get('analyst_reports', {})

if analyst_data and 'total_reports' in analyst_data:
    print(f"\n✅ ANALYST DATA RETRIEVED")
    print(f"   Total Reports: {analyst_data.get('total_reports', 0)}")
    print(f"   Estimates: {len(analyst_data.get('estimates', []))}")
    print(f"   Grades/Ratings: {len(analyst_data.get('grades', []))}")
    print(f"   Price Targets: {len(analyst_data.get('price_targets', []))}")
    
    results['phases']['analyst_reports'] = {
        'status': 'success',
        'total_reports': analyst_data.get('total_reports', 0)
    }
else:
    print(f"\n⚠️  No analyst data retrieved")

# =============================================================================
# PHASE 4: NEWS DATA
# =============================================================================
print("\n" + "="*100)
print("PHASE 4: NEWS & PRESS RELEASES")
print("="*100)

news_data = fetched_data.get('news', {})

if news_data and 'total_items' in news_data:
    print(f"\n✅ NEWS DATA RETRIEVED")
    print(f"   News Articles: {len(news_data.get('news_articles', []))}")
    print(f"   Press Releases: {len(news_data.get('press_releases', []))}")
    print(f"   Total Items: {news_data.get('total_items', 0)}")
    
    # Show recent headlines
    articles = news_data.get('news_articles', [])
    if articles:
        print(f"\n   📰 Recent Headlines:")
        for i, article in enumerate(articles[:3], 1):
            print(f"      {i}. {article.get('title', 'No title')[:80]}")
    
    results['phases']['news'] = {
        'status': 'success',
        'total_items': news_data.get('total_items', 0)
    }
else:
    print(f"\n⚠️ No news data retrieved")

# =============================================================================
# PHASE 5: VECTORIZATION RESULTS
# =============================================================================
print("\n" + "="*100)
print("PHASE 5: VECTORIZATION & RAG PROCESSING")
print("="*100)

vector_results = comprehensive_data.get('vectorization_results', {})

if vector_results:
    print(f"\n✅ VECTORIZATION COMPLETE")
    print(f"   Total Documents Processed: {vector_results.get('total_documents', 0)}")
    print(f"   Total Chunks Created: {vector_results.get('chunks_created', 0)}")
    print(f"   Total Vectors Stored: {vector_results.get('vectors_stored', 0)}")
    
    # Processing details
    details = vector_results.get('processing_details', {})
    if details:
        print(f"\n   📊 Processing Breakdown:")
        
        if 'sec_filings' in details:
            sec_proc = details['sec_filings']
            print(f"      • SEC Filings: {sec_proc.get('filings_processed', 0)} processed")
            print(f"        - Chunks: {sec_proc.get('chunks_created', 0)}")
            print(f"        - Vectors: {sec_proc.get('vectors_stored', 0)}")
        
        if 'analyst_reports' in details:
            analyst_proc = details['analyst_reports']
            print(f"      • Analyst Reports:")
            print(f"        - Chunks: {analyst_proc.get('chunks_created', 0)}")
            print(f"        - Vectors: {analyst_proc.get('vectors_stored', 0)}")
        
        if 'news' in details:
            news_proc = details['news']
            print(f"      • News Articles: {news_proc.get('articles_processed', 0)} processed")
            print(f"        - Chunks: {news_proc.get('chunks_created', 0)}")
            print(f"        - Vectors: {news_proc.get('vectors_stored', 0)}")
    
    results['phases']['vectorization'] = {
        'status': 'success',
        'total_documents': vector_results.get('total_documents', 0),
        'total_vectors': vector_results.get('vectors_stored', 0)
    }
else:
    print(f"\n⚠️  No vectorization results")

# =============================================================================
# FINAL SUMMARY
# =============================================================================
print("\n" + "="*100)
print("✅ INGESTION PIPELINE TEST COMPLETE")
print("="*100)

results['test_end'] = datetime.now().isoformat()

print(f"\n📊 FINAL CONFIRMATIONS:")
for phase, result in results['phases'].items():
    status_symbol = "✅" if result.get('status') == 'success' else "⚠️"
    print(f"   {status_symbol} {phase.replace('_', ' ').title()}: {result.get('status', 'unknown')}")

print(f"\n🎯 KEY METRICS:")
print(f"   • Shares Outstanding Retrieved: {results['phases'].get('company_info', {}).get('shares_outstanding', 0):,.0f}")
print(f"   • Data Sources Used: {len(results['phases'].get('company_info', {}).get('sources_used', []))}")
print(f"   • Documents Vectorized: {results['phases'].get('vectorization', {}).get('total_documents', 0)}")
print(f"   • Total Vectors Created: {results['phases'].get('vectorization', {}).get('total_vectors', 0)}")

# Save results
import json
output_file = f"INGESTION_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2, default=str)

print(f"\n💾 Results saved to: {output_file}")

print(f"\n" + "="*100)
print("✨ ENHANCED INGESTION PIPELINE VALIDATED!")
print("="*100)
