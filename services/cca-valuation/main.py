"""
CCA (Comparable Company Analysis) Valuation Service
Implements trading multiples valuation using peer company comparisons
Handles different company classifications and industry adjustments
"""

import os
import json
import logging
import numpy as np
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, List, Optional
from datetime import datetime
import statistics

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configurations
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')

class CCAValuationEngine:
    """Advanced Comparable Company Analysis engine"""

    def __init__(self):
        # Industry-specific valuation multiples (EV/Revenue, EV/EBITDA, P/E)
        self.industry_multiples = {
            'technology': {
                'ev_revenue': {'mean': 15.0, 'std': 5.0, 'min': 5.0, 'max': 40.0},  # Higher for hyper-growth tech
                'ev_ebitda': {'mean': 35.0, 'std': 12.0, 'min': 15.0, 'max': 80.0},  # Premium multiples
                'p_e': {'mean': 45.0, 'std': 18.0, 'min': 20.0, 'max': 100.0}  # High P/E for growth
            },
            'healthcare': {
                'ev_revenue': {'mean': 6.2, 'std': 1.8, 'min': 2.5, 'max': 15.0},
                'ev_ebitda': {'mean': 18.5, 'std': 6.2, 'min': 10.0, 'max': 35.0},
                'p_e': {'mean': 24.0, 'std': 8.0, 'min': 12.0, 'max': 45.0}
            },
            'financials': {
                'p_b': {'mean': 1.8, 'std': 0.6, 'min': 0.8, 'max': 3.5},
                'p_e': {'mean': 16.0, 'std': 4.0, 'min': 8.0, 'max': 25.0},
                'p_tbv': {'mean': 1.2, 'std': 0.3, 'min': 0.7, 'max': 2.0}
            },
            'energy': {
                'ev_revenue': {'mean': 2.8, 'std': 1.2, 'min': 1.0, 'max': 8.0},
                'ev_ebitda': {'mean': 8.5, 'std': 3.2, 'min': 4.0, 'max': 18.0},
                'p_e': {'mean': 18.0, 'std': 6.0, 'min': 8.0, 'max': 35.0}
            },
            'consumer_staples': {
                'ev_revenue': {'mean': 2.2, 'std': 0.8, 'min': 1.0, 'max': 5.0},
                'ev_ebitda': {'mean': 12.0, 'std': 3.5, 'min': 7.0, 'max': 20.0},
                'p_e': {'mean': 22.0, 'std': 5.0, 'min': 15.0, 'max': 30.0}
            },
            'industrials': {
                'ev_revenue': {'mean': 1.8, 'std': 0.7, 'min': 0.8, 'max': 4.0},
                'ev_ebitda': {'mean': 10.5, 'std': 3.0, 'min': 6.0, 'max': 18.0},
                'p_e': {'mean': 20.0, 'std': 5.0, 'min': 12.0, 'max': 30.0}
            }
        }

        # Growth stage adjustments
        self.growth_adjustments = {
            'hyper_growth': {'premium': 0.40, 'volatility': 1.5},  # 40% premium
            'growth': {'premium': 0.20, 'volatility': 1.2},        # 20% premium
            'mature_growth': {'premium': 0.05, 'volatility': 1.0}, # 5% premium
            'stable': {'premium': 0.00, 'volatility': 0.9},        # No adjustment
            'declining': {'premium': -0.15, 'volatility': 1.3},    # 15% discount
            'distressed': {'premium': -0.35, 'volatility': 1.8}    # 35% discount
        }

    def perform_cca_analysis(self, company_data: Dict[str, Any],
                           peers: List[Dict[str, Any]],
                           classification: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive comparable company analysis"""

        logger.info(f"Performing CCA analysis with {len(peers)} peers for classification: {classification.get('primary_classification')}")

        # Get company fundamentals
        company_fundamentals = self._extract_company_fundamentals(company_data)

        # Analyze peer companies
        peer_analysis = self._analyze_peer_companies(peers)

        # Calculate valuation multiples
        valuation_multiples = self._calculate_valuation_multiples(
            company_fundamentals, peer_analysis, classification
        )

        # Apply industry and growth adjustments
        adjusted_multiples = self._apply_adjustments(
            valuation_multiples, classification, company_data
        )

        # Calculate implied valuation
        implied_valuation = self._calculate_implied_valuation(
            adjusted_multiples, company_fundamentals
        )

        # Perform sensitivity analysis
        sensitivity_analysis = self._perform_sensitivity_analysis(
            adjusted_multiples, company_fundamentals
        )

        return {
            'company_fundamentals': company_fundamentals,
            'peer_analysis': peer_analysis,
            'valuation_multiples': valuation_multiples,
            'adjusted_multiples': adjusted_multiples,
            'implied_valuation': implied_valuation,
            'sensitivity_analysis': sensitivity_analysis,
            'methodology': 'comparable_company_analysis',
            'generated_at': datetime.now().isoformat()
        }

    def _extract_company_fundamentals(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key financial fundamentals for valuation"""

        financials = company_data.get('financials', {})
        market_data = company_data.get('market', {})
        company_info = company_data.get('company_info', {})

        # Get latest income statement
        income_stmts = financials.get('income_statements', [])
        if not income_stmts:
            income_stmts = company_info.get('income_statements', [])
        latest_income = income_stmts[0] if income_stmts else {}

        # Get latest balance sheet
        balance_stmts = financials.get('balance_sheets', [])
        if not balance_stmts:
            balance_stmts = company_info.get('balance_sheets', [])
        latest_balance = balance_stmts[0] if balance_stmts else {}

        # Calculate key metrics
        revenue = latest_income.get('revenue', 0)
        ebitda = self._calculate_ebitda(latest_income)
        net_income = latest_income.get('netIncome', 0)
        
        # Get shares outstanding from multiple sources
        shares_outstanding = company_info.get('sharesOutstanding', 0)
        if shares_outstanding == 0:
            shares_outstanding = market_data.get('sharesOutstanding', 0)
        if shares_outstanding == 0:
            yf_data = company_info.get('yfinance_data', {})
            shares_outstanding = yf_data.get('shares_outstanding', 0)

        # Enterprise value components
        market_cap = market_data.get('marketCap', 0)
        if market_cap == 0:
            yf_data = company_info.get('yfinance_data', {})
            market_cap = yf_data.get('market_cap', 0)
        
        cash = latest_balance.get('cashAndCashEquivalents', 0)
        debt = latest_balance.get('shortTermDebt', 0) + latest_balance.get('longTermDebt', 0)
        
        # Get price from multiple sources
        price_per_share = company_info.get('yfinance_data', {}).get('current_price', 0)
        if price_per_share == 0:
            price_per_share = market_data.get('price', 0)

        return {
            'revenue': revenue,
            'ebitda': ebitda,
            'net_income': net_income,
            'market_cap': market_cap,
            'cash': cash,
            'debt': debt,
            'enterprise_value': market_cap + debt - cash,
            'shares_outstanding': shares_outstanding,
            'price_per_share': price_per_share
        }

    def _calculate_ebitda(self, income_statement: Dict[str, Any]) -> float:
        """Calculate EBITDA from income statement"""
        try:
            operating_income = income_statement.get('operatingIncome', 0)
            depreciation = income_statement.get('depreciationAndAmortization', 0)
            # Estimate D&A if not available
            if depreciation == 0:
                depreciation = operating_income * 0.05  # Rough estimate

            ebitda = operating_income + depreciation
            return ebitda
        except Exception as e:
            logger.warning(f"Error calculating EBITDA: {e}")
            return 0

    def _analyze_peer_companies(self, peers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze peer companies and calculate statistics"""

        if not peers:
            return {'error': 'No peer companies available'}

        peer_metrics = []

        for peer in peers:
            # Extract peer fundamentals (simplified - in production would fetch full data)
            peer_fundamentals = {
                'symbol': peer.get('symbol', ''),
                'name': peer.get('companyName', ''),
                'market_cap': peer.get('marketCap', 0),
                'revenue': peer.get('revenue', 0),  # Would need to fetch actual data
                'ebitda': peer.get('ebitda', 0),    # Would need to fetch actual data
                'net_income': peer.get('netIncome', 0),
                'price': peer.get('price', 0),
                'sector': peer.get('sector', ''),
                'industry': peer.get('industry', '')
            }

            # Calculate multiples if data available
            if peer_fundamentals['revenue'] > 0:
                peer_fundamentals['ev_revenue'] = peer_fundamentals['market_cap'] / peer_fundamentals['revenue']

            if peer_fundamentals['ebitda'] > 0:
                peer_fundamentals['ev_ebitda'] = peer_fundamentals['market_cap'] / peer_fundamentals['ebitda']

            if peer_fundamentals['net_income'] > 0:
                peer_fundamentals['p_e'] = peer_fundamentals['market_cap'] / peer_fundamentals['net_income']

            peer_metrics.append(peer_fundamentals)

        # Calculate peer statistics
        peer_stats = self._calculate_peer_statistics(peer_metrics)

        return {
            'peer_companies': peer_metrics,
            'statistics': peer_stats,
            'peer_count': len(peer_metrics)
        }

    def _calculate_peer_statistics(self, peer_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistical measures for peer multiples"""

        multiples = ['ev_revenue', 'ev_ebitda', 'p_e']

        stats = {}

        for multiple in multiples:
            values = [p.get(multiple, 0) for p in peer_metrics if p.get(multiple, 0) > 0]

            if values:
                stats[multiple] = {
                    'mean': statistics.mean(values),
                    'median': statistics.median(values),
                    'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
                    'min': min(values),
                    'max': max(values),
                    'count': len(values),
                    'percentiles': {
                        '25th': np.percentile(values, 25),
                        '75th': np.percentile(values, 75)
                    }
                }
            else:
                stats[multiple] = {'error': 'Insufficient data'}

        return stats

    def _calculate_valuation_multiples(self, company_fundamentals: Dict[str, Any],
                                     peer_analysis: Dict[str, Any],
                                     classification: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate appropriate valuation multiples based on peers"""

        peer_stats = peer_analysis.get('statistics', {})

        multiples = {}

        # EV/Revenue multiple
        if 'ev_revenue' in peer_stats and peer_stats['ev_revenue'].get('mean'):
            multiples['ev_revenue'] = {
                'peer_mean': peer_stats['ev_revenue']['mean'],
                'peer_median': peer_stats['ev_revenue']['median'],
                'peer_range': [peer_stats['ev_revenue']['min'], peer_stats['ev_revenue']['max']],
                'recommended': peer_stats['ev_revenue']['median']  # Use median to reduce outlier impact
            }

        # EV/EBITDA multiple
        if 'ev_ebitda' in peer_stats and peer_stats['ev_ebitda'].get('mean'):
            multiples['ev_ebitda'] = {
                'peer_mean': peer_stats['ev_ebitda']['mean'],
                'peer_median': peer_stats['ev_ebitda']['median'],
                'peer_range': [peer_stats['ev_ebitda']['min'], peer_stats['ev_ebitda']['max']],
                'recommended': peer_stats['ev_ebitda']['median']
            }

        # P/E multiple
        if 'p_e' in peer_stats and peer_stats['p_e'].get('mean'):
            multiples['p_e'] = {
                'peer_mean': peer_stats['p_e']['mean'],
                'peer_median': peer_stats['p_e']['median'],
                'peer_range': [peer_stats['p_e']['min'], peer_stats['p_e']['max']],
                'recommended': peer_stats['p_e']['median']
            }

        # Industry-specific multiples
        industry_multiples = self._get_industry_multiples(classification, company_fundamentals)

        return {
            'peer_multiples': multiples,
            'industry_multiples': industry_multiples,
            'selected_multiples': self._select_best_multiples(multiples, industry_multiples, classification)
        }

    def _get_industry_multiples(self, classification: Dict[str, Any],
                              company_fundamentals: Dict[str, Any]) -> Dict[str, Any]:
        """Get industry-standard multiples"""

        # This would be enhanced with actual industry data
        # For now, using predefined ranges
        return self.industry_multiples

    def _select_best_multiples(self, peer_multiples: Dict[str, Any],
                             industry_multiples: Dict[str, Any],
                             classification: Dict[str, Any]) -> Dict[str, Any]:
        """Select the most appropriate multiples for valuation"""

        selected = {}
        
        # Get sector for industry multiples
        sector = classification.get('sector', 'Technology').lower()
        industry_data = industry_multiples.get(sector, industry_multiples.get('technology', {}))

        # Try each multiple type
        for multiple_type in ['ev_revenue', 'ev_ebitda', 'p_e']:
            # Try peer multiples first
            if multiple_type in peer_multiples:
                peer_value = peer_multiples[multiple_type].get('recommended', 0)
                if peer_value > 0:
                    selected[multiple_type] = peer_value
                    continue
            
            # Fall back to industry average
            multiple_data = industry_data.get(multiple_type, {})
            industry_mean = multiple_data.get('mean', 0)
            if industry_mean > 0:
                selected[multiple_type] = industry_mean

        return selected

    def _apply_adjustments(self, valuation_multiples: Dict[str, Any],
                         classification: Dict[str, Any],
                         company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply growth stage and company-specific adjustments"""

        selected_multiples = valuation_multiples.get('selected_multiples', {})
        adjusted_multiples = {}

        # Get growth adjustment
        growth_stage = classification.get('primary_classification', 'stable')
        growth_adj = self.growth_adjustments.get(growth_stage, {'premium': 0, 'volatility': 1})

        # Apply adjustments to each multiple
        for multiple_type, base_value in selected_multiples.items():
            if base_value > 0:
                # Apply growth premium/discount
                adjusted_value = base_value * (1 + growth_adj['premium'])

                # Apply size adjustment (smaller companies trade at discount)
                size_adjustment = self._calculate_size_adjustment(company_data)
                adjusted_value *= (1 + size_adjustment)

                # Apply profitability adjustment
                profitability_adj = self._calculate_profitability_adjustment(company_data)
                adjusted_value *= (1 + profitability_adj)

                adjusted_multiples[multiple_type] = {
                    'base_value': base_value,
                    'adjusted_value': adjusted_value,
                    'growth_adjustment': growth_adj['premium'],
                    'size_adjustment': size_adjustment,
                    'profitability_adjustment': profitability_adj,
                    'total_adjustment': growth_adj['premium'] + size_adjustment + profitability_adj
                }

        return adjusted_multiples

    def _calculate_size_adjustment(self, company_data: Dict[str, Any]) -> float:
        """Calculate size-based adjustment (smaller companies trade at discount)"""

        market_cap = company_data.get('market', {}).get('marketCap', 0)

        if market_cap >= 10000000000:  # $10B+
            return 0.05  # Premium for large caps
        elif market_cap >= 2000000000:  # $2B+
            return 0.00  # No adjustment
        elif market_cap >= 500000000:   # $500M+
            return -0.05  # Small discount
        else:
            return -0.15  # Significant discount for small caps

    def _calculate_profitability_adjustment(self, company_data: Dict[str, Any]) -> float:
        """Calculate profitability-based adjustment"""

        financials = company_data.get('financials', {})
        income_stmts = financials.get('income_statements', [])

        if not income_stmts:
            return 0

        latest_income = income_stmts[0]
        revenue = latest_income.get('revenue', 0)
        net_income = latest_income.get('netIncome', 0)

        if revenue == 0:
            return 0

        margin = net_income / revenue

        if margin > 0.25:      # High profitability
            return 0.10
        elif margin > 0.15:    # Good profitability
            return 0.05
        elif margin > 0.05:    # Moderate profitability
            return 0.00
        elif margin > 0:       # Low profitability
            return -0.05
        else:                  # Negative profitability
            return -0.15

    def _calculate_implied_valuation(self, adjusted_multiples: Dict[str, Any],
                                   company_fundamentals: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate implied valuation using adjusted multiples"""

        valuations = {}

        # EV/Revenue valuation
        if 'ev_revenue' in adjusted_multiples:
            multiple = adjusted_multiples['ev_revenue']['adjusted_value']
            revenue = company_fundamentals['revenue']
            enterprise_value = multiple * revenue

            valuations['ev_revenue'] = {
                'multiple': multiple,
                'metric_value': revenue,
                'enterprise_value': enterprise_value,
                'equity_value': enterprise_value - company_fundamentals['debt'] + company_fundamentals['cash'],
                'price_per_share': (enterprise_value - company_fundamentals['debt'] + company_fundamentals['cash']) / company_fundamentals['shares_outstanding'] if company_fundamentals['shares_outstanding'] > 0 else 0
            }

        # EV/EBITDA valuation
        if 'ev_ebitda' in adjusted_multiples:
            multiple = adjusted_multiples['ev_ebitda']['adjusted_value']
            ebitda = company_fundamentals['ebitda']
            enterprise_value = multiple * ebitda

            valuations['ev_ebitda'] = {
                'multiple': multiple,
                'metric_value': ebitda,
                'enterprise_value': enterprise_value,
                'equity_value': enterprise_value - company_fundamentals['debt'] + company_fundamentals['cash'],
                'price_per_share': (enterprise_value - company_fundamentals['debt'] + company_fundamentals['cash']) / company_fundamentals['shares_outstanding'] if company_fundamentals['shares_outstanding'] > 0 else 0
            }

        # P/E valuation
        if 'p_e' in adjusted_multiples:
            multiple = adjusted_multiples['p_e']['adjusted_value']
            net_income = company_fundamentals['net_income']
            equity_value = multiple * net_income

            valuations['p_e'] = {
                'multiple': multiple,
                'metric_value': net_income,
                'equity_value': equity_value,
                'price_per_share': equity_value / company_fundamentals['shares_outstanding'] if company_fundamentals['shares_outstanding'] > 0 else 0
            }

        # Calculate blended valuation
        blended_valuation = self._calculate_blended_valuation(valuations)

        return {
            'individual_valuations': valuations,
            'blended_valuation': blended_valuation,
            'current_price': company_fundamentals['price_per_share'],
            'upside_downside': self._calculate_upside_downside(blended_valuation, company_fundamentals)
        }

    def _calculate_blended_valuation(self, valuations: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate blended valuation from multiple methods"""

        price_estimates = []

        # Collect price per share estimates
        for method, valuation in valuations.items():
            if 'price_per_share' in valuation and valuation['price_per_share'] > 0:
                price_estimates.append(valuation['price_per_share'])

        if not price_estimates:
            return {'error': 'No valid valuations available'}

        blended_price = statistics.mean(price_estimates)

        return {
            'blended_price_per_share': blended_price,
            'valuation_methods_used': len(price_estimates),
            'price_range': [min(price_estimates), max(price_estimates)],
            'standard_deviation': statistics.stdev(price_estimates) if len(price_estimates) > 1 else 0
        }

    def _calculate_upside_downside(self, blended_valuation: Dict[str, Any],
                                 company_fundamentals: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate upside/downside to current price"""

        current_price = company_fundamentals['price_per_share']
        blended_price = blended_valuation.get('blended_price_per_share', 0)

        if current_price == 0 or blended_price == 0:
            return {'error': 'Insufficient data'}

        upside_downside_pct = (blended_price - current_price) / current_price

        return {
            'current_price': current_price,
            'implied_price': blended_price,
            'upside_downside_absolute': blended_price - current_price,
            'upside_downside_percent': upside_downside_pct,
            'direction': 'upside' if upside_downside_pct > 0 else 'downside'
        }

    def _perform_sensitivity_analysis(self, adjusted_multiples: Dict[str, Any],
                                   company_fundamentals: Dict[str, Any]) -> Dict[str, Any]:
        """Perform sensitivity analysis on key multiples"""

        sensitivity_results = {}

        # Test different multiple ranges
        for multiple_type, multiple_data in adjusted_multiples.items():
            base_value = multiple_data['adjusted_value']

            # Test -20% to +20% range
            multiple_range = np.linspace(base_value * 0.8, base_value * 1.2, 9)

            sensitivity = []
            for test_multiple in multiple_range:
                # Calculate implied value
                if multiple_type == 'ev_revenue':
                    metric = company_fundamentals['revenue']
                    ev = test_multiple * metric
                    equity_value = ev - company_fundamentals['debt'] + company_fundamentals['cash']
                    price_per_share = equity_value / company_fundamentals['shares_outstanding'] if company_fundamentals['shares_outstanding'] > 0 else 0
                elif multiple_type == 'ev_ebitda':
                    metric = company_fundamentals['ebitda']
                    ev = test_multiple * metric
                    equity_value = ev - company_fundamentals['debt'] + company_fundamentals['cash']
                    price_per_share = equity_value / company_fundamentals['shares_outstanding'] if company_fundamentals['shares_outstanding'] > 0 else 0
                elif multiple_type == 'p_e':
                    metric = company_fundamentals['net_income']
                    equity_value = test_multiple * metric
                    price_per_share = equity_value / company_fundamentals['shares_outstanding'] if company_fundamentals['shares_outstanding'] > 0 else 0
                else:
                    continue

                sensitivity.append({
                    'multiple': test_multiple,
                    'price_per_share': price_per_share
                })

            sensitivity_results[multiple_type] = sensitivity

        return sensitivity_results

    def perform_cca_valuation(self, target_symbol: str, target_financials: Dict[str, Any],
                             peer_companies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Simplified CCA valuation method for direct integration
        Wrapper around perform_cca_analysis with simpler interface
        """
        # Build company_data from target_financials - properly structure all data
        company_data = {
            'company_info': target_financials,  # Pass full company info
            'financials': {
                'income_statements': target_financials.get('income_statements', []),
                'balance_sheets': target_financials.get('balance_sheets', [])
            },
            'market': {
                'sharesOutstanding': target_financials.get('sharesOutstanding', 0),
                'marketCap': target_financials.get('yfinance_data', {}).get('market_cap', 0),
                'price': target_financials.get('yfinance_data', {}).get('current_price', 0)
            }
        }
        
        # Basic classification - use technology with hyper_growth for aggressive multiples
        classification = {
            'primary_classification': 'hyper_growth',  # Match the target classification
            'sector': target_financials.get('sector', 'Technology')
        }
        
        # Run full CCA analysis
        full_analysis = self.perform_cca_analysis(company_data, peer_companies, classification)
        
        # Return simplified result
        implied_val = full_analysis.get('implied_valuation', {})
        blended = implied_val.get('blended_valuation', {})
        individual_vals = implied_val.get('individual_valuations', {})
        
        # Get the best available valuation
        value_per_share = blended.get('blended_price_per_share', 0)
        
        # If blended is 0, try individual valuations
        if value_per_share == 0:
            for method in ['ev_revenue', 'ev_ebitda', 'p_e']:
                if method in individual_vals:
                    value_per_share = individual_vals[method].get('price_per_share', 0)
                    if value_per_share > 0:
                        break
        
        return {
            'implied_valuation': {
                'value_per_share': value_per_share,
                'enterprise_value': individual_vals.get('ev_revenue', {}).get('enterprise_value', 0),
                'equity_value': individual_vals.get('ev_revenue', {}).get('equity_value', 0)
            },
            'peer_count': len(peer_companies),
            'multiples_used': list(full_analysis.get('adjusted_multiples', {}).keys()),
            'detailed_analysis': full_analysis
        }

# Global CCA engine instance
cca_engine = CCAValuationEngine()

def require_api_key(f):
    """Decorator to require API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != SERVICE_API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'cca-valuation',
        'version': '1.0.0'
    })

@app.route('/valuation/cca', methods=['POST'])
@require_api_key
def perform_cca_valuation():
    """Perform comparable company analysis"""
    try:
        data = request.get_json()
        company_data = data.get('company_data', {})
        peers = data.get('peers', [])
        classification = data.get('classification', {})

        if not company_data:
            return jsonify({'error': 'Company data is required'}), 400

        valuation = cca_engine.perform_cca_analysis(
            company_data, peers, classification
        )

        return jsonify(valuation)

    except Exception as e:
        logger.error(f"Error performing CCA valuation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/valuation/peer-analysis', methods=['POST'])
@require_api_key
def analyze_peers():
    """Analyze peer companies"""
    try:
        data = request.get_json()
        peers = data.get('peers', [])

        analysis = cca_engine._analyze_peer_companies(peers)

        return jsonify(analysis)

    except Exception as e:
        logger.error(f"Error analyzing peers: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/valuation/multiples', methods=['POST'])
@require_api_key
def get_valuation_multiples():
    """Get valuation multiples for industry/sector"""
    try:
        data = request.get_json()
        sector = data.get('sector', '').lower()
        classification = data.get('classification', {})

        multiples = cca_engine.industry_multiples.get(sector, {})

        # Apply classification adjustments
        growth_stage = classification.get('primary_classification', 'stable')
        adjustments = cca_engine.growth_adjustments.get(growth_stage, {})

        adjusted_multiples = {}
        for multiple_type, multiple_data in multiples.items():
            base_mean = multiple_data.get('mean', 0)
            adjusted_mean = base_mean * (1 + adjustments.get('premium', 0))
            adjusted_multiples[multiple_type] = {
                'base_mean': base_mean,
                'adjusted_mean': adjusted_mean,
                'adjustment': adjustments.get('premium', 0),
                'range': [multiple_data.get('min', 0), multiple_data.get('max', 0)]
            }

        return jsonify({
            'sector': sector,
            'classification': growth_stage,
            'multiples': adjusted_multiples
        })

    except Exception as e:
        logger.error(f"Error getting valuation multiples: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
