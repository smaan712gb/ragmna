"""
Mergers Model Service
Handles merger and acquisition modeling including accretion/dilution analysis,
synergies valuation, and transaction structure optimization
"""

import os
import json
import logging
import numpy as np
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, List, Optional
from datetime import datetime
import copy

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configurations
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')

class MergersModelEngine:
    """Advanced mergers and acquisitions modeling engine"""

    def __init__(self):
        # Typical M&A transaction structures
        self.transaction_structures = {
            'stock_purchase': {
                'description': 'Buyer acquires all shares of target',
                'tax_implications': 'Asset sale treatment possible',
                'accounting': 'Purchase accounting'
            },
            'asset_purchase': {
                'description': 'Buyer acquires selected assets and liabilities',
                'tax_implications': 'Step-up in basis for assets',
                'accounting': 'Purchase accounting'
            },
            'merger': {
                'description': 'Legal combination of two entities',
                'tax_implications': 'Tax-free reorganization possible',
                'accounting': 'Purchase or pooling of interests'
            },
            'joint_venture': {
                'description': 'Creation of new entity owned by both parties',
                'tax_implications': 'Varies by structure',
                'accounting': 'Equity method or consolidation'
            }
        }

        # Synergy categories
        self.synergy_categories = {
            'cost_synergies': {
                'efficiency_gains': 0.15,  # 15% of combined cost base
                'procurement_savings': 0.05,  # 5% procurement savings
                'overhead_reduction': 0.08   # 8% overhead reduction
            },
            'revenue_synergies': {
                'cross_selling': 0.10,  # 10% revenue uplift
                'pricing_power': 0.03,  # 3% price increase
                'market_expansion': 0.12  # 12% market expansion
            }
        }

    def model_merger_acquisition(self, target_data: Dict[str, Any],
                               acquirer_data: Dict[str, Any],
                               transaction_params: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive merger/acquisition modeling"""

        logger.info(f"Modeling M&A transaction: {transaction_params.get('structure', 'unknown')}")

        # Extract financial data
        target_fundamentals = self._extract_fundamentals(target_data)
        acquirer_fundamentals = self._extract_fundamentals(acquirer_data)

        # Model transaction structure
        transaction_structure = self._model_transaction_structure(
            target_fundamentals, acquirer_fundamentals, transaction_params
        )

        # Calculate synergies
        synergies = self._calculate_synergies(
            target_fundamentals, acquirer_fundamentals, transaction_params
        )

        # Perform accretion/dilution analysis
        accretion_dilution = self._analyze_accretion_dilution(
            target_fundamentals, acquirer_fundamentals,
            transaction_structure, synergies, transaction_params
        )

        # Model combined entity
        combined_entity = self._model_combined_entity(
            target_fundamentals, acquirer_fundamentals,
            transaction_structure, synergies
        )

        # Risk assessment
        transaction_risks = self._assess_transaction_risks(
            target_fundamentals, acquirer_fundamentals, transaction_params
        )

        return {
            'transaction_structure': transaction_structure,
            'synergies': synergies,
            'accretion_dilution_analysis': accretion_dilution,
            'combined_entity': combined_entity,
            'transaction_risks': transaction_risks,
            'valuation_impact': self._calculate_valuation_impact(accretion_dilution, synergies),
            'generated_at': datetime.now().isoformat()
        }

    def _extract_fundamentals(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key financial fundamentals"""

        financials = company_data.get('financials', {})
        market = company_data.get('market', {})
        company_info = company_data.get('company_info', {})

        # Get latest income statement
        income_stmts = financials.get('income_statements', [])
        latest_income = income_stmts[0] if income_stmts else {}

        # Get latest balance sheet
        balance_stmts = financials.get('balance_sheets', [])
        latest_balance = balance_stmts[0] if balance_stmts else {}
        
        # Get shares outstanding from multiple sources - CRITICAL for valuation
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
        
        logger.info(f"✅ Using shares outstanding: {shares_outstanding:,.0f}")
        
        # Get price from multiple sources
        # Priority 1: Direct from company_info (FMP profile data)
        price_per_share = company_info.get('price', 0)
        logger.info(f"     Price source 1 - company_info.price: {price_per_share}")
        
        # Priority 2: yfinance current price
        if price_per_share == 0:
            price_per_share = company_info.get('yfinance_data', {}).get('current_price', 0)
            logger.info(f"     Price source 2 - yfinance_data.current_price: {price_per_share}")
        
        # Priority 3: market price
        if price_per_share == 0:
            price_per_share = market.get('price', 0)
            logger.info(f"     Price source 3 - market.price: {price_per_share}")
        
        # Priority 4: profile array
        if price_per_share == 0:
            profile = company_data.get('profile', [{}])
            if isinstance(profile, list) and len(profile) > 0:
                price_per_share = profile[0].get('price', 0)
                logger.info(f"     Price source 4 - profile[0].price: {price_per_share}")
        
        # Get market cap from FMP profile (current real-time value)
        market_cap = company_info.get('mktCap', 0)
        logger.info(f"     Market cap from company_info.mktCap: {market_cap}")
        
        # NO FALLBACK: Use only FMP profile mktCap (no calculations)

        return {
            'revenue': latest_income.get('revenue', 0),
            'ebitda': self._calculate_ebitda(latest_income),
            'net_income': latest_income.get('netIncome', 0),
            'total_assets': latest_balance.get('totalAssets', 0),
            'total_liabilities': latest_balance.get('totalLiabilities', 0),
            'shareholders_equity': latest_balance.get('totalStockholdersEquity', 0),
            'cash': latest_balance.get('cashAndCashEquivalents', 0),
            'debt': latest_balance.get('shortTermDebt', 0) + latest_balance.get('longTermDebt', 0),
            'shares_outstanding': shares_outstanding,
            'market_cap': market_cap,
            'price_per_share': price_per_share
        }

    def _calculate_ebitda(self, income_statement: Dict[str, Any]) -> float:
        """Calculate EBITDA"""
        operating_income = income_statement.get('operatingIncome', 0)
        depreciation = income_statement.get('depreciationAndAmortization', 0)

        # Estimate D&A if not available
        if depreciation == 0:
            depreciation = operating_income * 0.05

        return operating_income + depreciation

    def _model_transaction_structure(self, target: Dict[str, Any],
                                   acquirer: Dict[str, Any],
                                   params: Dict[str, Any]) -> Dict[str, Any]:
        """Model the transaction structure"""

        structure_type = params.get('structure', 'stock_purchase')
        purchase_price = params.get('purchase_price', target['market_cap'] * 1.25)  # 25% premium

        # Financing mix
        cash_portion = params.get('cash_portion', 0.6)  # 60% cash
        stock_portion = params.get('stock_portion', 0.4)  # 40% stock

        # Calculate exchange ratio if stock component
        exchange_ratio = 0
        if stock_portion > 0 and acquirer['shares_outstanding'] > 0 and acquirer['price_per_share'] > 0:
            exchange_ratio = (purchase_price * stock_portion) / (acquirer['price_per_share'] * acquirer['shares_outstanding'])

        # Transaction fees
        transaction_fees = purchase_price * 0.02  # 2% fees

        return {
            'structure_type': structure_type,
            'purchase_price': purchase_price,
            'equity_value': purchase_price,
            'enterprise_value': purchase_price + target['debt'] - target['cash'],
            'financing_mix': {
                'cash': cash_portion,
                'stock': stock_portion
            },
            'exchange_ratio': exchange_ratio,
            'transaction_fees': transaction_fees,
            'premium_paid': (purchase_price - target['market_cap']) / target['market_cap'] if target['market_cap'] > 0 else 0
        }

    def _calculate_synergies(self, target: Dict[str, Any],
                           acquirer: Dict[str, Any],
                           params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate expected synergies"""

        # Base synergy assumptions
        cost_synergies_pct = params.get('cost_synergies_pct', 0.08)  # 8% of combined costs
        revenue_synergies_pct = params.get('revenue_synergies_pct', 0.05)  # 5% revenue uplift

        # Combined entity metrics
        combined_revenue = target['revenue'] + acquirer['revenue']
        combined_ebitda = target['ebitda'] + acquirer['ebitda']

        # Cost synergies
        cost_synergies = combined_ebitda * cost_synergies_pct

        # Revenue synergies
        revenue_synergies = combined_revenue * revenue_synergies_pct

        # EBITDA impact
        ebitda_impact = cost_synergies + revenue_synergies

        # Timeline for synergy realization
        synergy_realization = {
            'year_1': 0.3,   # 30% in year 1
            'year_2': 0.5,   # 50% in year 2
            'year_3': 0.2    # 20% in year 3
        }

        return {
            'cost_synergies': cost_synergies,
            'revenue_synergies': revenue_synergies,
            'total_ebitda_impact': ebitda_impact,
            'realization_schedule': synergy_realization,
            'payback_period': self._calculate_synergy_payback(cost_synergies + revenue_synergies, params)
        }

    def _calculate_synergy_payback(self, annual_synergies: float, params: Dict[str, Any]) -> float:
        """Calculate payback period for synergies"""
        # Simplified - assumes synergies are invested evenly over 3 years
        total_investment = params.get('synergy_investment', annual_synergies * 1.5)  # 1.5x annual synergies

        if annual_synergies > 0:
            return total_investment / annual_synergies
        return float('inf')

    def _analyze_accretion_dilution(self, target: Dict[str, Any],
                                  acquirer: Dict[str, Any],
                                  transaction: Dict[str, Any],
                                  synergies: Dict[str, Any],
                                  params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze accretion/dilution to acquirer earnings"""

        # Pro forma combined entity
        combined_shares = acquirer['shares_outstanding']
        if transaction['financing_mix']['stock'] > 0:
            # Add shares issued for acquisition
            new_shares = (transaction['purchase_price'] * transaction['financing_mix']['stock']) / acquirer['price_per_share']
            combined_shares += new_shares

        # Pro forma EPS calculations
        acquirer_eps = acquirer['net_income'] / acquirer['shares_outstanding'] if acquirer['shares_outstanding'] > 0 else 0

        # Combined net income (with synergies)
        combined_net_income = acquirer['net_income'] + target['net_income'] + synergies['total_ebitda_impact'] * 0.7  # Assume 70% tax rate

        # Pro forma EPS
        pro_forma_eps = combined_net_income / combined_shares if combined_shares > 0 else 0

        # Accretion/dilution
        eps_change = pro_forma_eps - acquirer_eps
        if acquirer_eps == 0:
            raise ValueError("❌ Acquirer EPS is zero - cannot calculate accretion/dilution. Check acquirer net income and shares outstanding.")
        eps_accretion_dilution = eps_change / abs(acquirer_eps)

        return {
            'acquirer_eps': acquirer_eps,
            'pro_forma_eps': pro_forma_eps,
            'eps_change': eps_change,
            'eps_accretion_dilution': eps_accretion_dilution,
            'is_accretive': eps_change > 0,
            'combined_shares_outstanding': combined_shares,
            'synergy_impact_on_eps': (synergies['total_ebitda_impact'] * 0.7) / combined_shares if combined_shares > 0 else 0
        }

    def _model_combined_entity(self, target: Dict[str, Any],
                             acquirer: Dict[str, Any],
                             transaction: Dict[str, Any],
                             synergies: Dict[str, Any]) -> Dict[str, Any]:
        """Model the combined entity post-transaction"""

        # Combined financials
        combined = {
            'revenue': target['revenue'] + acquirer['revenue'],
            'ebitda': target['ebitda'] + acquirer['ebitda'] + synergies['total_ebitda_impact'],
            'net_income': target['net_income'] + acquirer['net_income'] + synergies['total_ebitda_impact'] * 0.7,
            'total_assets': target['total_assets'] + acquirer['total_assets'],
            'total_liabilities': target['total_liabilities'] + acquirer['total_liabilities'],
            'shareholders_equity': target['shareholders_equity'] + acquirer['shareholders_equity'] + synergies['total_ebitda_impact'] * 0.7,
            'cash': target['cash'] + acquirer['cash'] - transaction['purchase_price'] * transaction['financing_mix']['cash'],
            'debt': target['debt'] + acquirer['debt'] + transaction['purchase_price'] * transaction['financing_mix']['cash']
        }

        # Financial ratios
        ratios = {
            'debt_to_equity': combined['debt'] / combined['shareholders_equity'] if combined['shareholders_equity'] > 0 else 0,
            'debt_to_ebitda': combined['debt'] / combined['ebitda'] if combined['ebitda'] > 0 else 0,
            'ebitda_margin': combined['ebitda'] / combined['revenue'] if combined['revenue'] > 0 else 0,
            'net_margin': combined['net_income'] / combined['revenue'] if combined['revenue'] > 0 else 0
        }

        return {
            'combined_financials': combined,
            'financial_ratios': ratios,
            'credit_metrics': self._assess_credit_metrics(ratios),
            'size_category': self._determine_size_category(combined['revenue'])
        }

    def _assess_credit_metrics(self, ratios: Dict[str, Any]) -> Dict[str, Any]:
        """Assess credit quality of combined entity"""

        debt_to_ebitda = ratios['debt_to_ebitda']

        if debt_to_ebitda < 3:
            rating = 'BBB'
            quality = 'investment_grade'
        elif debt_to_ebitda < 5:
            rating = 'BB'
            quality = 'speculative'
        elif debt_to_ebitda < 7:
            rating = 'B'
            quality = 'highly_levered'
        else:
            rating = 'CCC'
            quality = 'distressed'

        return {
            'credit_rating': rating,
            'quality_assessment': quality,
            'debt_to_ebitda': debt_to_ebitda,
            'refinancing_needs': debt_to_ebitda > 6
        }

    def _determine_size_category(self, revenue: float) -> str:
        """Determine company size category"""

        if revenue > 50000000000:  # $50B
            return 'mega_cap'
        elif revenue > 10000000000:  # $10B
            return 'large_cap'
        elif revenue > 2000000000:   # $2B
            return 'mid_cap'
        elif revenue > 300000000:    # $300M
            return 'small_cap'
        else:
            return 'micro_cap'

    def _assess_transaction_risks(self, target: Dict[str, Any],
                                acquirer: Dict[str, Any],
                                params: Dict[str, Any]) -> Dict[str, Any]:
        """Assess transaction-specific risks"""

        risks = {
            'integration_risk': self._assess_integration_risk(target, acquirer),
            'financing_risk': self._assess_financing_risk(params),
            'regulatory_risk': self._assess_regulatory_risk(target, acquirer),
            'execution_risk': self._assess_execution_risk(params)
        }

        # Overall risk score
        risk_scores = [risk['severity_score'] for risk in risks.values()]
        overall_score = sum(risk_scores) / len(risk_scores)

        return {
            'risk_categories': risks,
            'overall_risk_score': overall_score,
            'risk_level': 'high' if overall_score > 3 else 'moderate' if overall_score > 2 else 'low',
            'mitigation_strategies': self._generate_risk_mitigation(risks)
        }

    def _assess_integration_risk(self, target: Dict[str, Any], acquirer: Dict[str, Any]) -> Dict[str, Any]:
        """Assess integration complexity and risk"""

        # Size difference
        size_ratio = min(target['revenue'], acquirer['revenue']) / max(target['revenue'], acquirer['revenue'])

        if size_ratio > 0.8:
            complexity = 'low'
            score = 1
        elif size_ratio > 0.5:
            complexity = 'moderate'
            score = 2
        elif size_ratio > 0.2:
            complexity = 'high'
            score = 3
        else:
            complexity = 'very_high'
            score = 4

        return {
            'complexity_level': complexity,
            'severity_score': score,
            'size_ratio': size_ratio,
            'integration_challenges': ['cultural_integration', 'system_integration', 'process_harmonization']
        }

    def _assess_financing_risk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Assess financing-related risks"""

        leverage = params.get('leverage_ratio', 4.0)

        if leverage < 3:
            risk_level = 'low'
            score = 1
        elif leverage < 5:
            risk_level = 'moderate'
            score = 2
        elif leverage < 7:
            risk_level = 'high'
            score = 3
        else:
            risk_level = 'very_high'
            score = 4

        return {
            'leverage_ratio': leverage,
            'risk_level': risk_level,
            'severity_score': score,
            'financing_concerns': ['interest_rate_risk', 'refinancing_risk', 'covenant_compliance']
        }

    def _assess_regulatory_risk(self, target: Dict[str, Any], acquirer: Dict[str, Any]) -> Dict[str, Any]:
        """Assess regulatory approval risks"""

        # Industry concentration
        combined_market_share = 0.15  # Placeholder - would need market data

        if combined_market_share < 0.2:
            risk_level = 'low'
            score = 1
        elif combined_market_share < 0.3:
            risk_level = 'moderate'
            score = 2
        elif combined_market_share < 0.4:
            risk_level = 'high'
            score = 3
        else:
            risk_level = 'very_high'
            score = 4

        return {
            'combined_market_share': combined_market_share,
            'risk_level': risk_level,
            'severity_score': score,
            'regulatory_hurdles': ['antitrust_review', 'CFIUS_review', 'foreign_investment_rules']
        }

    def _assess_execution_risk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Assess execution and timing risks"""

        # Deal complexity
        structure_complexity = len(params.get('special_conditions', []))

        if structure_complexity < 2:
            risk_level = 'low'
            score = 1
        elif structure_complexity < 4:
            risk_level = 'moderate'
            score = 2
        elif structure_complexity < 6:
            risk_level = 'high'
            score = 3
        else:
            risk_level = 'very_high'
            score = 4

        return {
            'structure_complexity': structure_complexity,
            'risk_level': risk_level,
            'severity_score': score,
            'execution_challenges': ['deal_timing', 'stakeholder_management', 'contingency_planning']
        }

    def _generate_risk_mitigation(self, risks: Dict[str, Any]) -> List[str]:
        """Generate risk mitigation strategies"""

        mitigation = []

        for risk_type, risk_data in risks.items():
            if risk_data['severity_score'] >= 3:
                if risk_type == 'integration_risk':
                    mitigation.extend([
                        'Develop detailed integration plan with milestones',
                        'Establish integration management office',
                        'Conduct cultural assessment and change management'
                    ])
                elif risk_type == 'financing_risk':
                    mitigation.extend([
                        'Secure committed financing before announcement',
                        'Include financing contingencies in agreement',
                        'Monitor interest rate environment'
                    ])
                elif risk_type == 'regulatory_risk':
                    mitigation.extend([
                        'Engage antitrust counsel early',
                        'Prepare regulatory filings in advance',
                        'Develop divestiture plan if needed'
                    ])
                elif risk_type == 'execution_risk':
                    mitigation.extend([
                        'Build execution timeline with buffers',
                        'Identify key decision makers and stakeholders',
                        'Develop contingency plans for delays'
                    ])

        return list(set(mitigation))  # Remove duplicates

    def _calculate_valuation_impact(self, accretion_dilution: Dict[str, Any],
                                  synergies: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall valuation impact"""

        eps_impact = accretion_dilution['eps_accretion_dilution']
        synergy_value = synergies['total_ebitda_impact'] * 8  # 8x EBITDA multiple

        return {
            'eps_impact': eps_impact,
            'synergy_value': synergy_value,
            'total_value_creation': synergy_value * (1 + eps_impact),
            'value_creation_per_share': (synergy_value * (1 + eps_impact)) / 1000000000,  # Per billion in transaction value
            'break_even_synergy': 0.05  # 5% of transaction value needed for break-even
        }

    def analyze_merger(self, acquirer_symbol: str, target_symbol: str,
                      acquirer_financials: Dict[str, Any], target_financials: Dict[str, Any],
                      offer_price_per_share: float, synergies: float,
                      deal_structure: str = 'cash_and_stock') -> Dict[str, Any]:
        """
        Simplified merger analysis method for direct integration
        Wrapper around model_merger_acquisition with simpler interface
        """
        # Build data structures
        target_data = {'financials': {}, 'market': {}}
        acquirer_data = {'financials': {}, 'market': {}}
        
        transaction_params = {
            'structure': deal_structure,
            'purchase_price': offer_price_per_share,
            'cash_portion': 0.6,
            'stock_portion': 0.4
        }
        
        # Run full merger model
        full_analysis = self.model_merger_acquisition(target_data, acquirer_data, transaction_params)
        
        # Return simplified result
        accretion_dilution = full_analysis.get('accretion_dilution_analysis', {})
        combined = full_analysis.get('combined_entity', {}).get('combined_financials', {})
        
        return {
            'eps_accretion_dilution': accretion_dilution.get('eps_accretion_dilution', 0) * 100,  # As percentage
            'synergies': synergies,
            'combined_revenue': combined.get('revenue', 0),
            'combined_ebitda': combined.get('ebitda', 0),
            'pro_forma_eps': accretion_dilution.get('pro_forma_eps', 0),
            'is_accretive': accretion_dilution.get('is_accretive', False),
            'detailed_analysis': full_analysis
        }

# Global mergers model engine instance
mergers_engine = MergersModelEngine()

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
        'service': 'mergers-model',
        'version': '1.0.0'
    })

@app.route('/model/ma', methods=['POST'])
@require_api_key
def model_merger_acquisition():
    """Model merger or acquisition transaction"""
    try:
        data = request.get_json()
        target_data = data.get('target_data', {})
        acquirer_data = data.get('acquirer_data', {})
        transaction_params = data.get('transaction_params', {})

        if not target_data or not acquirer_data:
            return jsonify({'error': 'Target and acquirer data are required'}), 400

        model = mergers_engine.model_merger_acquisition(
            target_data, acquirer_data, transaction_params
        )

        return jsonify(model)

    except Exception as e:
        logger.error(f"Error modeling M&A transaction: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/model/accretion-dilution', methods=['POST'])
@require_api_key
def analyze_accretion_dilution():
    """Analyze accretion/dilution impact"""
    try:
        data = request.get_json()
        target_data = data.get('target_data', {})
        acquirer_data = data.get('acquirer_data', {})
        transaction_params = data.get('transaction_params', {})

        # Extract fundamentals
        target_fundamentals = mergers_engine._extract_fundamentals(target_data)
        acquirer_fundamentals = mergers_engine._extract_fundamentals(acquirer_data)

        # Model transaction
        transaction = mergers_engine._model_transaction_structure(
            target_fundamentals, acquirer_fundamentals, transaction_params
        )

        # Calculate synergies
        synergies = mergers_engine._calculate_synergies(
            target_fundamentals, acquirer_fundamentals, transaction_params
        )

        # Analyze accretion/dilution
        analysis = mergers_engine._analyze_accretion_dilution(
            target_fundamentals, acquirer_fundamentals,
            transaction, synergies, transaction_params
        )

        return jsonify({
            'transaction_structure': transaction,
            'synergies': synergies,
            'accretion_dilution': analysis
        })

    except Exception as e:
        logger.error(f"Error analyzing accretion/dilution: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/model/synergies', methods=['POST'])
@require_api_key
def calculate_synergies():
    """Calculate expected synergies"""
    try:
        data = request.get_json()
        target_data = data.get('target_data', {})
        acquirer_data = data.get('acquirer_data', {})
        synergy_params = data.get('synergy_params', {})

        # Extract fundamentals
        target_fundamentals = mergers_engine._extract_fundamentals(target_data)
        acquirer_fundamentals = mergers_engine._extract_fundamentals(acquirer_data)

        synergies = mergers_engine._calculate_synergies(
            target_fundamentals, acquirer_fundamentals, synergy_params
        )

        return jsonify(synergies)

    except Exception as e:
        logger.error(f"Error calculating synergies: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/model/risks', methods=['POST'])
@require_api_key
def assess_transaction_risks():
    """Assess transaction risks"""
    try:
        data = request.get_json()
        target_data = data.get('target_data', {})
        acquirer_data = data.get('acquirer_data', {})
        transaction_params = data.get('transaction_params', {})

        # Extract fundamentals
        target_fundamentals = mergers_engine._extract_fundamentals(target_data)
        acquirer_fundamentals = mergers_engine._extract_fundamentals(acquirer_data)

        risks = mergers_engine._assess_transaction_risks(
            target_fundamentals, acquirer_fundamentals, transaction_params
        )

        return jsonify(risks)

    except Exception as e:
        logger.error(f"Error assessing transaction risks: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
