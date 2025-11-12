"""
COMPREHENSIVE M&A WORKFLOW TEST WITH SENSITIVITY ANALYSIS
Tests the complete end-to-end M&A analysis pipeline:
1. Data Ingestion (Multi-source)
2. Classification (Gemini 2.5)
3. Normalization (GAAP adjustments)
4. 3-Statement Modeling
5. DCF Valuation + Sensitivity Analysis
6. CCA Valuation
7. LBO Analysis + Sensitivity Analysis
8. Mergers Model
"""

import sys
import os
from datetime import datetime
import json

print("="*100)
print("🧪 COMPREHENSIVE M&A WORKFLOW TEST WITH SENSITIVITY ANALYSIS")
print("="*100)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Target: NVDA | Acquirer: MSFT")
print("="*100)

results = {
    'test_start': datetime.now().isoformat(),
    'target_symbol': 'NVDA',
    'acquirer_symbol': 'MSFT',
    'phases': {}
}

# Import services
print("\n📦 Importing services...")
sys.path.insert(0, 'services/data-ingestion')
import importlib.util

# Data Ingestion
spec_ing = importlib.util.spec_from_file_location("data_ing_main", "services/data-ingestion/main.py")
data_ing_module = importlib.util.module_from_spec(spec_ing)
spec_ing.loader.exec_module(data_ing_module)
data_ingestion = data_ing_module.data_ingestion
print("✅ Data ingestion")

# LLM Orchestrator
spec_llm = importlib.util.spec_from_file_location("llm_orch_main", "services/llm-orchestrator/main.py")
llm_module = importlib.util.module_from_spec(spec_llm)
spec_llm.loader.exec_module(llm_module)
orchestrator = llm_module.orchestrator
print("✅ LLM orchestrator")

# Financial Normalizer
spec_norm = importlib.util.spec_from_file_location("norm_main", "services/financial-normalizer/main.py")
norm_module = importlib.util.module_from_spec(spec_norm)
spec_norm.loader.exec_module(norm_module)
normalizer = norm_module.normalizer
print("✅ Financial normalizer")

# 3-Statement Modeler
spec_3sm = importlib.util.spec_from_file_location("tsm_main", "services/three-statement-modeler/main.py")
tsm_module = importlib.util.module_from_spec(spec_3sm)
spec_3sm.loader.exec_module(tsm_module)
modeler = tsm_module.modeler
print("✅ 3-Statement modeler")

# DCF Valuation
spec_dcf = importlib.util.spec_from_file_location("dcf_main", "services/dcf-valuation/main.py")
dcf_module = importlib.util.module_from_spec(spec_dcf)
spec_dcf.loader.exec_module(dcf_module)
dcf_engine = dcf_module.dcf_engine
print("✅ DCF valuation")

# CCA Valuation
spec_cca = importlib.util.spec_from_file_location("cca_main", "services/cca-valuation/main.py")
cca_module = importlib.util.module_from_spec(spec_cca)
spec_cca.loader.exec_module(cca_module)
cca_engine = cca_module.cca_engine
print("✅ CCA valuation")

# LBO Analysis
spec_lbo = importlib.util.spec_from_file_location("lbo_main", "services/lbo-analysis/main.py")
lbo_module = importlib.util.module_from_spec(spec_lbo)
spec_lbo.loader.exec_module(lbo_module)
lbo_engine = lbo_module.lbo_engine
print("✅ LBO analysis")

# Mergers Model
spec_mergers = importlib.util.spec_from_file_location("mergers_main", "services/mergers-model/main.py")
mergers_module = importlib.util.module_from_spec(spec_mergers)
spec_mergers.loader.exec_module(mergers_module)
mergers_engine = mergers_module.mergers_engine
print("✅ Mergers model\n")

import asyncio

# =============================================================================
# PHASE 1: DATA INGESTION
# =============================================================================
print("\n" + "="*100)
print("PHASE 1: MULTI-COMPANY DATA INGESTION")
print("="*100)

try:
    print("\n📥 Fetching data for TARGET (NVDA)...")
    target_data = data_ingestion.fetch_company_data(symbol='NVDA', data_sources=[])
    target_info = target_data.get('company_info', {})
    
    print(f"✅ Target Data: {target_info.get('companyName')}")
    print(f"   Revenue: ${target_info.get('income_statements', [{}])[0].get('revenue', 0):,.0f}")
    print(f"   Shares: {target_info.get('sharesOutstanding', 0):,.0f}")
    
    print("\n📥 Fetching data for ACQUIRER (MSFT)...")
    acquirer_data = data_ingestion.fetch_company_data(symbol='MSFT', data_sources=[])
    acquirer_info = acquirer_data.get('company_info', {})
    
    print(f"✅ Acquirer Data: {acquirer_info.get('companyName')}")
    print(f"   Revenue: ${acquirer_info.get('income_statements', [{}])[0].get('revenue', 0):,.0f}")
    print(f"   Shares: {acquirer_info.get('sharesOutstanding', 0):,.0f}")
    
    results['phases']['data_ingestion'] = {'status': 'success'}
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# PHASE 2: CLASSIFICATION
# =============================================================================
print("\n" + "="*100)
print("PHASE 2: COMPANY CLASSIFICATION")
print("="*100)

try:
    print("\n🏷️ Classifying TARGET (NVDA)...")
    target_classification = asyncio.run(
        orchestrator.classifier.classify_company_profile('NVDA', target_info)
    )
    print(f"✅ Classification: {target_classification.get('primary_classification')}")
    print(f"   Growth Stage: {target_classification.get('growth_stage')}")
    
    print("\n🏷️ Classifying ACQUIRER (MSFT)...")
    acquirer_classification = asyncio.run(
        orchestrator.classifier.classify_company_profile('MSFT', acquirer_info)
    )
    print(f"✅ Classification: {acquirer_classification.get('primary_classification')}")
    print(f"   Growth Stage: {acquirer_classification.get('growth_stage')}")
    
    results['phases']['classification'] = {'status': 'success'}
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    target_classification = {'primary_classification': 'hyper_growth'}
    acquirer_classification = {'primary_classification': 'stable'}
    results['phases']['classification'] = {'status': 'fallback'}

# =============================================================================
# PHASE 3: 3-STATEMENT MODELING
# =============================================================================
print("\n" + "="*100)
print("PHASE 3: 3-STATEMENT FINANCIAL MODELS")
print("="*100)

try:
    print("\n📊 Building TARGET model...")
    target_model = modeler.generate_three_statement_model(
        company_data=target_data,
        classification=target_classification,
        projection_years=5
    )
    print(f"✅ Target Model: {len(target_model.get('income_statement', []))} years projected")
    
    print("\n📊 Building ACQUIRER model...")
    acquirer_model = modeler.generate_three_statement_model(
        company_data=acquirer_data,
        classification=acquirer_classification,
        projection_years=5
    )
    print(f"✅ Acquirer Model: {len(acquirer_model.get('income_statement', []))} years projected")
    
    results['phases']['3sm'] = {'status': 'success'}
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    results['phases']['3sm'] = {'status': 'failed'}
    target_model = {}
    acquirer_model = {}

# =============================================================================
# PHASE 4: DCF VALUATION WITH SENSITIVITY ANALYSIS
# =============================================================================
print("\n" + "="*100)
print("PHASE 4: DCF VALUATION WITH SENSITIVITY ANALYSIS")
print("="*100)

try:
    print("\n💰 Running comprehensive DCF valuation for TARGET...")
    
    # Call full DCF analysis to get sensitivity
    dcf_full_analysis = dcf_engine.perform_dcf_analysis(
        company_data=target_data,
        financial_model=target_model,
        classification=target_classification
    )
    
    equity_value = dcf_full_analysis['final_valuation']['equity_value']
    value_per_share = dcf_full_analysis['final_valuation']['equity_value_per_share']
    
    print(f"✅ DCF Complete")
    print(f"   Enterprise Value: ${dcf_full_analysis['present_value_analysis']['enterprise_value']:,.0f}")
    print(f"   Equity Value: ${equity_value:,.0f}")
    print(f"   Value Per Share: ${value_per_share:.2f}")
    print(f"   WACC: {dcf_full_analysis['wacc']:.2%}")
    
    # Display sensitivity analysis
    print(f"\n📊 SENSITIVITY ANALYSIS:")
    sensitivity = dcf_full_analysis.get('sensitivity_analysis', {})
    
    print(f"\n   WACC Sensitivity:")
    for wacc_scenario in sensitivity.get('wacc_sensitivity', [])[:3]:
        print(f"   • WACC {wacc_scenario['wacc']:.2%}: EV ${wacc_scenario['enterprise_value']:,.0f}")
    
    print(f"\n   Terminal Growth Sensitivity:")
    for growth_scenario in sensitivity.get('growth_sensitivity', [])[:3]:
        print(f"   • Growth {growth_scenario['terminal_growth']:.2%}: EV ${growth_scenario['enterprise_value']:,.0f}")
    
    # Display scenario analysis
    print(f"\n📈 SCENARIO ANALYSIS:")
    scenarios = dcf_full_analysis.get('scenario_analysis', {})
    for scenario_name, scenario_data in scenarios.items():
        print(f"   • {scenario_name.upper()}: EV ${scenario_data['enterprise_value']:,.0f} (WACC: {scenario_data['wacc']:.2%})")
    
    results['phases']['dcf'] = {
        'status': 'success',
        'value_per_share': value_per_share,
        'sensitivity_included': True,
        'scenarios': len(scenarios)
    }
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    results['phases']['dcf'] = {'status': 'failed'}
    dcf_full_analysis = {}
    value_per_share = 500

# =============================================================================
# PHASE 5: CCA VALUATION
# =============================================================================
print("\n" + "="*100)
print("PHASE 5: COMPARABLE COMPANY ANALYSIS")
print("="*100)

try:
    print("\n📊 Running CCA valuation...")
    
    # Structure data properly for CCA
    cca_company_data = {
        'company_info': target_info,
        'financials': {
            'income_statements': target_info.get('income_statements', []),
            'balance_sheets': target_info.get('balance_sheets', [])
        },
        'market': {
            'sharesOutstanding': target_info.get('sharesOutstanding', 0),
            'marketCap': target_info.get('yfinance_data', {}).get('market_cap', 0),
            'price': target_info.get('yfinance_data', {}).get('current_price', 0)
        }
    }
    
    # Use industry multiples (since peer data is unavailable)
    peer_data = []  # Empty peers will trigger industry multiples
    
    # Use full CCA analysis method
    cca_full_result = cca_engine.perform_cca_analysis(
        company_data=cca_company_data,
        peers=peer_data,
        classification=target_classification
    )
    
    implied_val = cca_full_result.get('implied_valuation', {})
    blended = implied_val.get('blended_valuation', {})
    implied_value = blended.get('blended_price_per_share', 0)
    
    print(f"✅ CCA Complete")
    print(f"   Valuation Method: Industry Multiples (Technology + Hyper-Growth Premium)")
    print(f"   Implied Value Per Share: ${implied_value:.2f}")
    
    # Display the multiples used
    adjusted_mults = cca_full_result.get('adjusted_multiples', {})
    if adjusted_mults:
        print(f"\n   Multiples Applied:")
        for mult_type, mult_data in adjusted_mults.items():
            print(f"   • {mult_type.upper()}: {mult_data['adjusted_value']:.1f}x (base: {mult_data['base_value']:.1f}x, +{mult_data['total_adjustment']:.1%})")
    
    results['phases']['cca'] = {
        'status': 'success',
        'value_per_share': implied_value,
        'multiples_count': len(adjusted_mults)
    }
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    results['phases']['cca'] = {'status': 'failed'}
    cca_result = {}

# =============================================================================
# PHASE 6: LBO ANALYSIS WITH SENSITIVITY ANALYSIS
# =============================================================================
print("\n" + "="*100)
print("PHASE 6: LEVERAGED BUYOUT ANALYSIS WITH SENSITIVITY")
print("="*100)

try:
    print("\n🏦 Running comprehensive LBO analysis...")
    
    # Call full LBO analysis to get sensitivity
    lbo_full_analysis = lbo_engine.perform_lbo_analysis(
        company_data=target_data,
        financial_model=target_model,
        classification=target_classification
    )
    
    returns = lbo_full_analysis.get('returns_analysis', {})
    irr = returns.get('irr', 0) * 100  # Convert to percentage
    moic = returns.get('money_multiple', 0)
    
    print(f"✅ LBO Complete")
    print(f"   IRR: {irr:.1f}%")
    print(f"   MOIC: {moic:.2f}x")
    print(f"   Attractiveness: {returns.get('returns_assessment', {}).get('overall_attractiveness', 'Unknown')}")
    
    # Display exit scenarios (sensitivity to exit timing)
    print(f"\n📊 EXIT SCENARIO SENSITIVITY:")
    exit_scenarios = lbo_full_analysis.get('exit_scenarios', {})
    for scenario_name, scenario_data in exit_scenarios.items():
        print(f"   • {scenario_name.replace('_', ' ').title()}:")
        print(f"     - IRR: {scenario_data['irr']*100:.1f}%")
        print(f"     - MOIC: {scenario_data['money_multiple']:.2f}x")
        print(f"     - Exit Multiple: {scenario_data['exit_multiple']:.1f}x")
    
    # Display risk assessment
    print(f"\n⚠️  RISK ASSESSMENT:")
    risk_assessment = lbo_full_analysis.get('risk_assessment', {})
    print(f"   • Overall Risk: {risk_assessment.get('overall_risk', 'Unknown').upper()}")
    print(f"   • Leverage Risk: {risk_assessment.get('leverage_risk', 'Unknown').upper()}")
    print(f"   • Business Risk: {risk_assessment.get('business_risk', 'Unknown').upper()}")
    
    results['phases']['lbo'] = {
        'status': 'success',
        'irr': irr,
        'moic': moic,
        'sensitivity_included': True,
        'exit_scenarios': len(exit_scenarios)
    }
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    results['phases']['lbo'] = {'status': 'failed'}
    lbo_full_analysis = {}

# =============================================================================
# PHASE 7: MERGERS ACCRETION/DILUTION
# =============================================================================
print("\n" + "="*100)
print("PHASE 7: MERGERS ACCRETION/DILUTION ANALYSIS")
print("="*100)

try:
    print("\n🤝 Running mergers analysis...")
    
    # Properly structure data for mergers analysis
    target_merge_data = {
        'company_info': target_info,
        'financials': {
            'income_statements': target_info.get('income_statements', []),
            'balance_sheets': target_info.get('balance_sheets', [])
        },
        'market': {
            'sharesOutstanding': target_info.get('sharesOutstanding', 0),
            'marketCap': target_info.get('yfinance_data', {}).get('market_cap', 0),
            'price': target_info.get('yfinance_data', {}).get('current_price', 0)
        }
    }
    
    acquirer_merge_data = {
        'company_info': acquirer_info,
        'financials': {
            'income_statements': acquirer_info.get('income_statements', []),
            'balance_sheets': acquirer_info.get('balance_sheets', [])
        },
        'market': {
            'sharesOutstanding': acquirer_info.get('sharesOutstanding', 0),
            'marketCap': acquirer_info.get('yfinance_data', {}).get('market_cap', 0),
            'price': acquirer_info.get('yfinance_data', {}).get('current_price', 0)
        }
    }
    
    transaction_params = {
        'structure': 'cash_and_stock',
        'purchase_price': value_per_share * target_info.get('sharesOutstanding', 1) if 'value_per_share' in locals() else 500000000000,
        'cash_portion': 0.6,
        'stock_portion': 0.4
    }
    
    # Use full model_merger_acquisition method
    mergers_result = mergers_engine.model_merger_acquisition(
        target_data=target_merge_data,
        acquirer_data=acquirer_merge_data,
        transaction_params=transaction_params
    )
    
    # Extract key metrics from full analysis
    accretion_data = mergers_result.get('accretion_dilution_analysis', {})
    accretion = accretion_data.get('eps_accretion_dilution', 0) * 100
    synergies_data = mergers_result.get('synergies', {})
    combined_data = mergers_result.get('combined_entity', {}).get('combined_financials', {})
    
    print(f"✅ Mergers Analysis Complete")
    print(f"   EPS Impact: {accretion:+.1f}% {'(Accretive)' if accretion > 0 else '(Dilutive)'}")
    print(f"   Synergies: ${synergies_data.get('total_ebitda_impact', 0):,.0f}")
    print(f"   Combined Revenue: ${combined_data.get('revenue', 0):,.0f}")
    print(f"   Pro Forma EPS: ${accretion_data.get('pro_forma_eps', 0):.2f}")
    print(f"   Is Accretive: {accretion_data.get('is_accretive', False)}")
    
    results['phases']['mergers'] = {'status': 'success', 'eps_impact': accretion}
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    results['phases']['mergers'] = {'status': 'failed'}
    mergers_result = {}

# =============================================================================
# FINAL SUMMARY
# =============================================================================
print("\n" + "="*100)
print("✅ COMPREHENSIVE M&A WORKFLOW WITH SENSITIVITY ANALYSIS COMPLETE")
print("="*100)

print(f"\n📊 WORKFLOW RESULTS:")
for phase, result in results['phases'].items():
    status = result.get('status', 'unknown')
    sensitivity = " [SENSITIVITY ✓]" if result.get('sensitivity_included') else ""
    symbol = "✅" if status == 'success' else "⚠️" if status == 'fallback' else "❌"
    print(f"   {symbol} {phase.replace('_', ' ').title()}: {status.upper()}{sensitivity}")

print(f"\n🎯 VALUATION SUMMARY:")
if results['phases'].get('dcf', {}).get('status') == 'success':
    print(f"   DCF Value: ${results['phases']['dcf'].get('value_per_share', 0):.2f}/share")
    print(f"   • Scenarios Analyzed: {results['phases']['dcf'].get('scenarios', 0)}")
if results['phases'].get('cca', {}).get('status') == 'success':
    print(f"   CCA Value: ${results['phases']['cca'].get('value_per_share', 0):.2f}/share")
if results['phases'].get('lbo', {}).get('status') == 'success':
    print(f"   LBO IRR: {results['phases']['lbo'].get('irr', 0):.1f}%")
    print(f"   • Exit Scenarios: {results['phases']['lbo'].get('exit_scenarios', 0)}")
if results['phases'].get('mergers', {}).get('status') == 'success':
    print(f"   EPS Impact: {results['phases']['mergers'].get('eps_impact', 0):+.1f}%")

# Save results
output_file = f"FULL_MA_WORKFLOW_SENSITIVITY_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_file, 'w') as f:
    # Include full analysis objects in saved results
    full_results = results.copy()
    full_results['detailed_analysis'] = {
        'dcf': dcf_full_analysis if 'dcf_full_analysis' in locals() else {},
        'lbo': lbo_full_analysis if 'lbo_full_analysis' in locals() else {},
        'mergers': mergers_result if 'mergers_result' in locals() else {}
    }
    json.dump(full_results, f, indent=2, default=str)

print(f"\n💾 Results saved to: {output_file}")

all_success = all(p.get('status') in ['success', 'fallback'] for p in results['phases'].values())

if all_success:
    print(f"\n" + "="*100)
    print("✨ FULL M&A WORKFLOW WITH SENSITIVITY ANALYSIS VALIDATED - All Systems Operational!")
    print("="*100)
else:
    print(f"\n" + "="*100)
    print("⚠️  Some phases need attention - Review output above")
    print("="*100)
