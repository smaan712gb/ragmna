"""
LBO (Leveraged Buyout) Analysis Service
Implements comprehensive LBO modeling with debt structures, IRR calculations, and exit scenarios
Handles different financing structures and risk assessments for leveraged acquisitions
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

class LBOAnalysisEngine:
    """Advanced LBO analysis engine with multiple financing scenarios"""

    def __init__(self):
        # Typical LBO financing structures by company type
        self.financing_structures = {
            'hyper_growth': {
                'senior_debt': 0.3,    # 30% senior debt
                'subordinate_debt': 0.2,  # 20% subordinated
                'equity': 0.5,        # 50% equity
                'interest_rate_senior': 0.08,
                'interest_rate_sub': 0.12,
                'fees': 0.03          # 3% fees
            },
            'growth': {
                'senior_debt': 0.4,
                'subordinate_debt': 0.2,
                'equity': 0.4,
                'interest_rate_senior': 0.07,
                'interest_rate_sub': 0.11,
                'fees': 0.025
            },
            'mature_growth': {
                'senior_debt': 0.5,
                'subordinate_debt': 0.15,
                'equity': 0.35,
                'interest_rate_senior': 0.06,
                'interest_rate_sub': 0.10,
                'fees': 0.02
            },
            'stable': {
                'senior_debt': 0.55,
                'subordinate_debt': 0.10,
                'equity': 0.35,
                'interest_rate_senior': 0.055,
                'interest_rate_sub': 0.09,
                'fees': 0.015
            },
            'declining': {
                'senior_debt': 0.4,
                'subordinate_debt': 0.1,
                'equity': 0.5,
                'interest_rate_senior': 0.08,
                'interest_rate_sub': 0.13,
                'fees': 0.035
            },
            'distressed': {
                'senior_debt': 0.3,
                'subordinate_debt': 0.1,
                'equity': 0.6,
                'interest_rate_senior': 0.10,
                'interest_rate_sub': 0.15,
                'fees': 0.04
            }
        }

        # Exit multiples by industry and time horizon
        self.exit_multiples = {
            '3_year': {'technology': 12.0, 'healthcare': 10.0, 'industrials': 8.0},
            '5_year': {'technology': 10.0, 'healthcare': 8.5, 'industrials': 7.0},
            '7_year': {'technology': 8.0, 'healthcare': 7.0, 'industrials': 6.0}
        }

    def perform_lbo_analysis(self, company_data: Dict[str, Any],
                           financial_model: Dict[str, Any],
                           classification: Dict[str, Any],
                           purchase_price: float = None) -> Dict[str, Any]:
        """Perform comprehensive LBO analysis"""

        logger.info(f"Performing LBO analysis for classification: {classification.get('primary_classification')}")

        # Determine purchase price if not provided
        if purchase_price is None:
            purchase_price = self._estimate_purchase_price(company_data, classification)

        # Get financing structure
        financing = self._get_financing_structure(classification, purchase_price)

        # Build LBO model
        lbo_model = self._build_lbo_model(
            company_data, financial_model, financing, purchase_price
        )

        # Calculate returns
        returns_analysis = self._calculate_returns(lbo_model, classification)

        # Risk assessment
        risk_assessment = self._assess_lbo_risks(lbo_model, financing, classification)

        # Exit scenarios
        exit_scenarios = self._analyze_exit_scenarios(lbo_model, classification)

        return {
            'purchase_price': purchase_price,
            'financing_structure': financing,
            'lbo_model': lbo_model,
            'returns_analysis': returns_analysis,
            'risk_assessment': risk_assessment,
            'exit_scenarios': exit_scenarios,
            'summary': self._generate_lbo_summary(lbo_model, returns_analysis),
            'generated_at': datetime.now().isoformat()
        }

    def _estimate_purchase_price(self, company_data: Dict[str, Any],
                               classification: Dict[str, Any]) -> float:
        """Estimate purchase price based on valuation analysis"""

        # Use market cap as starting point, adjusted for control premium
        market_data = company_data.get('market', {})
        market_cap = market_data.get('marketCap', 0)

        if market_cap == 0:
            return 1000000000  # Default $1B for modeling

        # Control premium by classification
        control_premiums = {
            'hyper_growth': 0.20,   # 20% premium
            'growth': 0.25,         # 25% premium
            'mature_growth': 0.30,  # 30% premium
            'stable': 0.35,         # 35% premium
            'declining': 0.15,      # 15% premium
            'distressed': 0.05      # 5% premium
        }

        primary_class = classification.get('primary_classification', 'stable')
        control_premium = control_premiums.get(primary_class, 0.30)

        return market_cap * (1 + control_premium)

    def _get_financing_structure(self, classification: Dict[str, Any],
                               purchase_price: float) -> Dict[str, Any]:
        """Determine optimal financing structure"""

        primary_class = classification.get('primary_classification', 'stable')
        base_structure = self.financing_structures.get(primary_class, self.financing_structures['stable'])

        # Calculate dollar amounts
        senior_debt = purchase_price * base_structure['senior_debt']
        subordinate_debt = purchase_price * base_structure['subordinate_debt']
        equity = purchase_price * base_structure['equity']
        fees = purchase_price * base_structure['fees']

        # Total financing needed
        total_financing = senior_debt + subordinate_debt + equity + fees

        return {
            'senior_debt': {
                'amount': senior_debt,
                'percentage': base_structure['senior_debt'],
                'interest_rate': base_structure['interest_rate_senior']
            },
            'subordinate_debt': {
                'amount': subordinate_debt,
                'percentage': base_structure['subordinate_debt'],
                'interest_rate': base_structure['interest_rate_sub']
            },
            'equity': {
                'amount': equity,
                'percentage': base_structure['equity']
            },
            'fees': {
                'amount': fees,
                'percentage': base_structure['fees']
            },
            'total_financing': total_financing,
            'leverage_ratio': (senior_debt + subordinate_debt) / equity if equity > 0 else 0
        }

    def _build_lbo_model(self, company_data: Dict[str, Any],
                        financial_model: Dict[str, Any],
                        financing: Dict[str, Any],
                        purchase_price: float) -> Dict[str, Any]:
        """Build comprehensive LBO financial model"""

        # Extract cash flows from financial model
        cash_flows = []
        cf_statement = financial_model.get('cash_flow_statement', [])

        for cf in cf_statement:
            operating_cf = cf.get('operating_cash_flow', 0)
            capex = cf.get('capex', 0)
            free_cash_flow = operating_cf - capex
            cash_flows.append(free_cash_flow)

        # Debt schedule
        debt_schedule = self._build_debt_schedule(financing, cash_flows)

        # Equity cash flows (available for distribution)
        equity_cash_flows = []
        cumulative_paid = 0

        for i, fcf in enumerate(cash_flows):
            year = i + 1

            # Interest payments
            senior_interest = financing['senior_debt']['amount'] * financing['senior_debt']['interest_rate']
            sub_interest = financing['subordinate_debt']['amount'] * financing['subordinate_debt']['interest_rate']
            total_interest = senior_interest + sub_interest

            # Principal payments (simplified - equal payments)
            senior_principal = financing['senior_debt']['amount'] / len(cash_flows)
            sub_principal = financing['subordinate_debt']['amount'] / len(cash_flows)

            # Total debt service
            debt_service = total_interest + senior_principal + sub_principal

            # Cash available for equity
            equity_cf = fcf - debt_service

            # Cumulative distributions (simplified - pay if positive)
            if equity_cf > 0:
                cumulative_paid += equity_cf
                distribution = equity_cf
            else:
                distribution = 0

            equity_cash_flows.append({
                'year': year,
                'free_cash_flow': fcf,
                'interest_payments': total_interest,
                'principal_payments': senior_principal + sub_principal,
                'debt_service': debt_service,
                'equity_cash_flow': equity_cf,
                'cumulative_distributions': cumulative_paid,
                'distribution': distribution
            })

        return {
            'purchase_price': purchase_price,
            'financing': financing,
            'debt_schedule': debt_schedule,
            'equity_cash_flows': equity_cash_flows,
            'exit_assumptions': self._get_exit_assumptions(financial_model)
        }

    def _build_debt_schedule(self, financing: Dict[str, Any],
                           cash_flows: List[float]) -> Dict[str, Any]:
        """Build detailed debt repayment schedule"""

        senior_debt = financing['senior_debt']['amount']
        sub_debt = financing['subordinate_debt']['amount']

        # Simplified equal principal payments
        senior_payment = senior_debt / len(cash_flows)
        sub_payment = sub_debt / len(cash_flows)

        senior_balance = senior_debt
        sub_balance = sub_debt

        schedule = []

        for year in range(1, len(cash_flows) + 1):
            senior_interest = senior_balance * financing['senior_debt']['interest_rate']
            sub_interest = sub_balance * financing['subordinate_debt']['interest_rate']

            # Update balances
            senior_balance = max(0, senior_balance - senior_payment)
            sub_balance = max(0, sub_balance - sub_payment)

            schedule.append({
                'year': year,
                'senior_debt_balance': senior_balance,
                'subordinate_debt_balance': sub_balance,
                'total_debt_balance': senior_balance + sub_balance,
                'senior_interest': senior_interest,
                'subordinate_interest': sub_interest,
                'total_interest': senior_interest + sub_interest
            })

        return {'schedule': schedule}

    def _calculate_returns(self, lbo_model: Dict[str, Any],
                         classification: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate IRR and multiples for equity investors"""

        equity_investment = lbo_model['financing']['equity']['amount']
        equity_cash_flows = lbo_model['equity_cash_flows']

        # Build cash flow stream for IRR calculation
        cf_stream = [-equity_investment]  # Initial investment (negative)

        for cf in equity_cash_flows:
            cf_stream.append(cf['distribution'])

        # Add exit proceeds (simplified - assume final year distribution)
        final_year_cf = equity_cash_flows[-1]['cumulative_distributions']
        cf_stream[-1] += final_year_cf  # Add to final year

        # Calculate IRR
        try:
            irr = self._calculate_irr(cf_stream)
        except:
            irr = 0

        # Calculate multiples
        total_distributions = sum(cf['distribution'] for cf in equity_cash_flows)
        total_investment = equity_investment

        money_multiple = (total_distributions + final_year_cf) / total_investment if total_investment > 0 else 0

        return {
            'irr': irr,
            'money_multiple': money_multiple,
            'total_investment': total_investment,
            'total_distributions': total_distributions + final_year_cf,
            'equity_cash_flows': cf_stream,
            'payback_period': self._calculate_payback_period(cf_stream),
            'returns_assessment': self._assess_returns(irr, money_multiple, classification)
        }

    def _calculate_irr(self, cash_flows: List[float], guess: float = 0.1) -> float:
        """Calculate IRR using Newton-Raphson method"""

        def npv(rate):
            return sum(cf / ((1 + rate) ** i) for i, cf in enumerate(cash_flows))

        def npv_derivative(rate):
            return sum(-i * cf / ((1 + rate) ** (i + 1)) for i, cf in enumerate(cash_flows))

        # Newton-Raphson iteration
        rate = guess
        for _ in range(100):
            f = npv(rate)
            f_prime = npv_derivative(rate)

            if abs(f_prime) < 1e-10:
                break

            rate = rate - f / f_prime

            if not (0 <= rate <= 1):
                rate = guess
                break

        return rate

    def _calculate_payback_period(self, cash_flows: List[float]) -> float:
        """Calculate payback period in years"""

        cumulative = 0
        initial_investment = abs(cash_flows[0])

        for i, cf in enumerate(cash_flows[1:], 1):
            cumulative += cf
            if cumulative >= initial_investment:
                # Linear interpolation for partial year
                excess = cumulative - initial_investment
                if excess > 0 and i < len(cash_flows) - 1:
                    return i - 1 + (excess / cf)
                return i

        return float('inf')  # Never pays back

    def _assess_returns(self, irr: float, money_multiple: float,
                       classification: Dict[str, Any]) -> Dict[str, Any]:
        """Assess attractiveness of returns"""

        primary_class = classification.get('primary_classification', 'stable')

        # Hurdle rates by classification
        hurdle_rates = {
            'hyper_growth': 0.25,    # 25% IRR required
            'growth': 0.22,          # 22%
            'mature_growth': 0.18,   # 18%
            'stable': 0.15,          # 15%
            'declining': 0.20,       # 20% (higher risk)
            'distressed': 0.30       # 30% (very high risk)
        }

        hurdle_rate = hurdle_rates.get(primary_class, 0.20)

        # Money multiple thresholds
        money_multiple_thresholds = {
            'hyper_growth': 2.5,
            'growth': 2.2,
            'mature_growth': 1.8,
            'stable': 1.5,
            'declining': 2.0,
            'distressed': 3.0
        }

        money_threshold = money_multiple_thresholds.get(primary_class, 2.0)

        # Assessment
        irr_attractive = irr >= hurdle_rate
        multiple_attractive = money_multiple >= money_threshold

        overall_attractiveness = "attractive" if (irr_attractive and multiple_attractive) else "marginal" if (irr_attractive or multiple_attractive) else "unattractive"

        return {
            'irr_hurdle_rate': hurdle_rate,
            'money_multiple_threshold': money_threshold,
            'irr_attractive': irr_attractive,
            'multiple_attractive': multiple_attractive,
            'overall_attractiveness': overall_attractiveness,
            'required_improvements': self._suggest_improvements(irr, money_multiple, hurdle_rate, money_threshold)
        }

    def _suggest_improvements(self, irr: float, money_multiple: float,
                            hurdle_rate: float, money_threshold: float) -> List[str]:
        """Suggest ways to improve LBO returns"""

        suggestions = []

        if irr < hurdle_rate:
            suggestions.append("Consider higher leverage to increase returns")
            suggestions.append("Look for operational improvements to boost cash flows")
            suggestions.append("Explore faster debt paydown schedules")

        if money_multiple < money_threshold:
            suggestions.append("Seek higher exit multiples through better market timing")
            suggestions.append("Consider longer hold periods for value creation")
            suggestions.append("Implement cost reduction initiatives")

        if not suggestions:
            suggestions.append("LBO returns meet or exceed requirements")

        return suggestions

    def _assess_lbo_risks(self, lbo_model: Dict[str, Any],
                        financing: Dict[str, Any],
                        classification: Dict[str, Any]) -> Dict[str, Any]:
        """Assess LBO-specific risks"""

        leverage_ratio = financing.get('leverage_ratio', 0)
        primary_class = classification.get('primary_classification', 'stable')

        # Leverage risk
        if leverage_ratio > 6:
            leverage_risk = "very_high"
        elif leverage_ratio > 4:
            leverage_risk = "high"
        elif leverage_ratio > 3:
            leverage_risk = "moderate"
        else:
            leverage_risk = "low"

        # Business risk based on classification
        business_risks = {
            'hyper_growth': 'high',     # Volatile growth
            'growth': 'moderate_high',  # Scaling challenges
            'mature_growth': 'moderate', # Competitive pressures
            'stable': 'low',            # Predictable cash flows
            'declining': 'high',        # Market share loss
            'distressed': 'very_high'   # Turnaround risk
        }

        business_risk = business_risks.get(primary_class, 'moderate')

        # Debt service coverage
        equity_cfs = lbo_model.get('equity_cash_flows', [])
        coverage_ratios = []

        for cf in equity_cfs:
            debt_service = cf.get('debt_service', 0)
            fcf = cf.get('free_cash_flow', 0)
            coverage = fcf / debt_service if debt_service > 0 else float('inf')
            coverage_ratios.append(coverage)

        avg_coverage = np.mean(coverage_ratios) if coverage_ratios else 0
        min_coverage = min(coverage_ratios) if coverage_ratios else 0

        # Overall risk assessment
        risk_factors = [leverage_risk, business_risk]
        risk_scores = {'low': 1, 'moderate': 2, 'moderate_high': 3, 'high': 4, 'very_high': 5}

        avg_risk_score = np.mean([risk_scores.get(risk, 3) for risk in risk_factors])

        if avg_risk_score >= 4:
            overall_risk = "high"
        elif avg_risk_score >= 3:
            overall_risk = "moderate_high"
        elif avg_risk_score >= 2:
            overall_risk = "moderate"
        else:
            overall_risk = "low"

        return {
            'leverage_risk': leverage_risk,
            'business_risk': business_risk,
            'debt_service_coverage': {
                'average': avg_coverage,
                'minimum': min_coverage,
                'ratios': coverage_ratios
            },
            'overall_risk': overall_risk,
            'risk_mitigation': self._suggest_risk_mitigation(overall_risk, leverage_ratio)
        }

    def _suggest_risk_mitigation(self, overall_risk: str, leverage_ratio: float) -> List[str]:
        """Suggest risk mitigation strategies"""

        suggestions = []

        if overall_risk in ['high', 'very_high']:
            suggestions.append("Consider reducing leverage to improve debt service coverage")
            suggestions.append("Implement interest rate hedging strategies")
            suggestions.append("Build cash reserves for operational flexibility")

        if leverage_ratio > 5:
            suggestions.append("Add covenant-lite debt structures for flexibility")
            suggestions.append("Secure equity cure rights for covenant breaches")

        suggestions.append("Develop detailed operational improvement plans")
        suggestions.append("Create multiple exit scenarios and timing flexibility")

        return suggestions

    def _analyze_exit_scenarios(self, lbo_model: Dict[str, Any],
                             classification: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze different exit scenarios"""

        # Get exit assumptions
        exit_assumptions = lbo_model.get('exit_assumptions', {})

        # Different exit timelines
        exit_timelines = [3, 5, 7]  # years

        scenarios = {}

        for timeline in exit_timelines:
            # Estimate exit valuation
            exit_multiple = self._get_exit_multiple(classification, timeline)
            final_fcf = lbo_model['equity_cash_flows'][min(timeline-1, len(lbo_model['equity_cash_flows'])-1)]['free_cash_flow']

            exit_value = final_fcf * exit_multiple

            # Pay down remaining debt
            remaining_debt = self._calculate_remaining_debt(lbo_model, timeline)
            equity_proceeds = exit_value - remaining_debt

            # Calculate returns
            equity_investment = lbo_model['financing']['equity']['amount']
            total_return = equity_proceeds + sum(cf['distribution'] for cf in lbo_model['equity_cash_flows'][:timeline])

            irr = self._calculate_exit_irr(equity_investment, lbo_model['equity_cash_flows'][:timeline], equity_proceeds)

            scenarios[f'{timeline}_year_exit'] = {
                'exit_multiple': exit_multiple,
                'exit_value': exit_value,
                'remaining_debt': remaining_debt,
                'equity_proceeds': equity_proceeds,
                'total_return': total_return,
                'irr': irr,
                'money_multiple': total_return / equity_investment if equity_investment > 0 else 0
            }

        return scenarios

    def _get_exit_multiple(self, classification: Dict[str, Any], timeline: int) -> float:
        """Get appropriate exit multiple based on timeline and classification"""

        primary_class = classification.get('primary_classification', 'stable')
        sector = classification.get('sector', 'industrials').lower()

        # Get base multiple for timeline
        timeline_key = f'{timeline}_year'
        sector_multiples = self.exit_multiples.get(timeline_key, {})

        base_multiple = sector_multiples.get(sector, 8.0)

        # Adjust for classification
        classification_adjustments = {
            'hyper_growth': 1.5,   # Higher multiples for growth
            'growth': 1.2,
            'mature_growth': 1.0,
            'stable': 0.9,
            'declining': 0.7,
            'distressed': 0.5
        }

        adjustment = classification_adjustments.get(primary_class, 1.0)

        return base_multiple * adjustment

    def _calculate_remaining_debt(self, lbo_model: Dict[str, Any], timeline: int) -> float:
        """Calculate remaining debt at exit"""

        debt_schedule = lbo_model['debt_schedule']['schedule']

        if timeline <= len(debt_schedule):
            year_data = debt_schedule[timeline - 1]
            return year_data.get('total_debt_balance', 0)

        # If beyond schedule, assume fully paid
        return 0

    def _calculate_exit_irr(self, equity_investment: float,
                          cash_flows: List[Dict[str, Any]],
                          exit_proceeds: float) -> float:
        """Calculate IRR including exit proceeds"""

        cf_stream = [-equity_investment]

        for cf in cash_flows:
            cf_stream.append(cf.get('distribution', 0))

        cf_stream.append(exit_proceeds)

        try:
            return self._calculate_irr(cf_stream)
        except:
            return 0

    def _get_exit_assumptions(self, financial_model: Dict[str, Any]) -> Dict[str, Any]:
        """Get exit valuation assumptions"""

        return {
            'methodology': 'exit_multiple_method',
            'assumptions': 'Based on industry comparables and market conditions',
            'sensitivity': 'Multiples vary by market conditions and company performance'
        }

    def _generate_lbo_summary(self, lbo_model: Dict[str, Any],
                            returns_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate executive summary of LBO analysis"""

        financing = lbo_model['financing']
        irr = returns_analysis.get('irr', 0)
        money_multiple = returns_analysis.get('money_multiple', 0)

        return {
            'purchase_price': lbo_model['purchase_price'],
            'equity_investment': financing['equity']['amount'],
            'leverage_ratio': financing.get('leverage_ratio', 0),
            'irr': irr,
            'money_multiple': money_multiple,
            'payback_period': returns_analysis.get('payback_period', 0),
            'key_assumptions': {
                'senior_debt_ratio': financing['senior_debt']['percentage'],
                'subordinate_debt_ratio': financing['subordinate_debt']['percentage'],
                'equity_ratio': financing['equity']['percentage'],
                'senior_interest_rate': financing['senior_debt']['interest_rate'],
                'subordinate_interest_rate': financing['subordinate_debt']['interest_rate']
            },
            'recommendation': "attractive" if irr > 0.15 and money_multiple > 1.5 else "requires_improvement"
        }

    def analyze_lbo(self, target_symbol: str, target_financials: Dict[str, Any],
                   purchase_price_multiple: float = 15.0, debt_to_equity: float = 0.6,
                   exit_multiple: float = 12.0, holding_period: int = 5) -> Dict[str, Any]:
        """
        Simplified LBO analysis method for direct integration
        Wrapper around perform_lbo_analysis with simpler interface
        """
        # Build company_data and classification
        company_data = {'market': {}, 'financials': {}}
        classification = {'primary_classification': target_financials.get('classification', 'stable')}
        
        # Run full LBO analysis
        full_analysis = self.perform_lbo_analysis(company_data, target_financials, classification)
        
        # Return simplified result
        returns = full_analysis.get('returns_analysis', {})
        summary = full_analysis.get('summary', {})
        
        return {
            'irr': returns.get('irr', 0) * 100,  # Convert to percentage
            'moic': returns.get('money_multiple', 0),
            'payback_period': returns.get('payback_period', 0),
            'equity_investment': summary.get('equity_investment', 0),
            'purchase_price': summary.get('purchase_price', 0),
            'leverage_ratio': summary.get('leverage_ratio', 0),
            'feasibility': summary.get('recommendation', 'unknown'),
            'detailed_analysis': full_analysis
        }

# Global LBO engine instance
lbo_engine = LBOAnalysisEngine()

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
        'service': 'lbo-analysis',
        'version': '1.0.0'
    })

@app.route('/analysis/lbo', methods=['POST'])
@require_api_key
def perform_lbo_analysis():
    """Perform LBO analysis"""
    try:
        data = request.get_json()
        company_data = data.get('company_data', {})
        financial_model = data.get('financial_model', {})
        classification = data.get('classification', {})
        purchase_price = data.get('purchase_price')

        if not company_data or not financial_model:
            return jsonify({'error': 'Company data and financial model are required'}), 400

        analysis = lbo_engine.perform_lbo_analysis(
            company_data, financial_model, classification, purchase_price
        )

        return jsonify(analysis)

    except Exception as e:
        logger.error(f"Error performing LBO analysis: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/analysis/lbo/scenarios', methods=['POST'])
@require_api_key
def analyze_lbo_scenarios():
    """Analyze multiple LBO financing scenarios"""
    try:
        data = request.get_json()
        base_analysis = data.get('base_analysis', {})
        scenarios = data.get('scenarios', [])

        results = []

        for scenario in scenarios:
            # Modify financing structure
            modified_financing = copy.deepcopy(base_analysis.get('financing_structure', {}))

            # Apply scenario adjustments
            for component, adjustment in scenario.get('adjustments', {}).items():
                if component in modified_financing:
                    modified_financing[component]['percentage'] *= adjustment

            # Recalculate analysis with new financing
            scenario_result = lbo_engine.perform_lbo_analysis(
                base_analysis.get('company_data', {}),
                base_analysis.get('financial_model', {}),
                base_analysis.get('classification', {}),
                modified_financing
            )

            results.append({
                'scenario_name': scenario.get('name', 'Unnamed'),
                'financing_structure': modified_financing,
                'results': scenario_result
            })

        return jsonify({'scenario_analysis': results})

    except Exception as e:
        logger.error(f"Error analyzing LBO scenarios: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/analysis/lbo/sensitivity', methods=['POST'])
@require_api_key
def lbo_sensitivity_analysis():
    """Perform sensitivity analysis on LBO assumptions"""
    try:
        data = request.get_json()
        base_analysis = data.get('base_analysis', {})
        sensitivity_vars = data.get('sensitivity_variables', {})

        # Default sensitivity variables
        if not sensitivity_vars:
            sensitivity_vars = {
                'purchase_price': [-0.1, 0, 0.1],  # -10% to +10%
                'exit_multiple': [-0.2, 0, 0.2],    # -20% to +20%
                'interest_rate': [-0.02, 0, 0.02]  # -200bps to +200bps
            }

        sensitivity_results = {}

        for var_name, changes in sensitivity_vars.items():
            var_results = []

            for change in changes:
                # Apply sensitivity change
                modified_data = copy.deepcopy(base_analysis)

                if var_name == 'purchase_price':
                    modified_data['purchase_price'] *= (1 + change)
                elif var_name == 'exit_multiple':
                    # Modify exit assumptions
                    if 'exit_scenarios' in modified_data:
                        for scenario, scenario_data in modified_data['exit_scenarios'].items():
                            scenario_data['exit_multiple'] *= (1 + change)
                elif var_name == 'interest_rate':
                    # Modify interest rates
                    if 'financing_structure' in modified_data:
                        financing = modified_data['financing_structure']
                        financing['senior_debt']['interest_rate'] += change
                        financing['subordinate_debt']['interest_rate'] += change

                # Recalculate analysis
                result = lbo_engine.perform_lbo_analysis(
                    modified_data.get('company_data', {}),
                    modified_data.get('financial_model', {}),
                    modified_data.get('classification', {}),
                    modified_data.get('purchase_price')
                )

                var_results.append({
                    'change': change,
                    'irr': result.get('returns_analysis', {}).get('irr', 0),
                    'money_multiple': result.get('returns_analysis', {}).get('money_multiple', 0)
                })

            sensitivity_results[var_name] = var_results

        return jsonify({'sensitivity_analysis': sensitivity_results})

    except Exception as e:
        logger.error(f"Error performing LBO sensitivity analysis: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
