"""Synthetic Stage D facts test the contract, not legal extraction accuracy."""
from copy import deepcopy
import pytest


def answer():
    return {
        'parties': [
            {'party_id': 'p1', 'name': 'Borrower Ltd', 'roles': ['borrower'],
             'status': 'supported', 'evidence_item_ids': ['#/texts/0']},
            {'party_id': 'p2', 'name': 'Lender Ltd', 'roles': ['lender'],
             'status': 'supported', 'evidence_item_ids': ['#/texts/1']},
            {'party_id': 'p3', 'name': 'Parent Ltd', 'roles': [],
             'status': 'supported', 'evidence_item_ids': ['#/texts/0']}
        ],
        'relationships': [{'parent_party_id': 'p3', 'child_party_id': 'p1',
            'status': 'supported', 'evidence_item_ids': ['#/texts/0']}],
        'facilities': [{'facility_id': 'f1', 'type': 'term_loan', 'currency': 'USD',
            'amount': {'value': 13_000_000, 'kind': 'commitment', 'status': 'supported',
                       'evidence_item_ids': ['#/texts/1']},
            'lender_commitments': [{'lender_party_id': 'p2', 'amount': 13_000_000,
                'status': 'supported', 'evidence_item_ids': ['#/texts/1']}]}],
        'interest': [{'facility_id': 'f1', 'rate_type': 'floating', 'benchmark': 'SOFR',
            'margin_rate': 0.04, 'benchmark_floor_rate': 0.01,
            'formula': 'max(benchmark_rate, 0.01) + 0.04',
            'total_rate': {'value': None, 'status': 'missing_inputs',
                           'missing_inputs': ['applicable_benchmark_rate']},
            'payment_frequency': 'quarterly', 'day_count': 'ACT/360',
            'evidence_item_ids': ['#/texts/2']}],
        'issues': []
    }


def validate(value):
    from credit_agreement_extractor.extraction_models import validate_extraction
    return validate_extraction(value, {'#/texts/0', '#/texts/1', '#/texts/2'})


def test_agreed_shape_and_numeric_rates_without_mutation():
    value = answer(); before = deepcopy(value)
    result = validate(value)
    assert result['parties'][2]['roles'] == []
    assert result['interest'][0]['margin_rate'] == 0.04
    assert result['interest'][0]['total_rate']['value'] is None
    assert value == before


@pytest.mark.parametrize('number', ['0.04', True, float('nan'), float('inf'), -0.04])
def test_invalid_numeric_rates_rejected(number):
    value = answer(); value['interest'][0]['margin_rate'] = number
    with pytest.raises(ValueError): validate(value)


@pytest.mark.parametrize('mutate', [
    lambda x: x['parties'][0].update(name=' '),
    lambda x: x['parties'][0].update(status='found'),
    lambda x: x['parties'][0].update(evidence_item_ids=[]),
    lambda x: x['parties'][0].update(evidence_item_ids=['#/texts/99']),
    lambda x: x['parties'][0].update(extra='ignored?'),
    lambda x: x['parties'][1].update(party_id='p1'),
    lambda x: x['parties'][1].update(name='Borrower Ltd'),
    lambda x: x['relationships'][0].update(child_party_id='unknown'),
    lambda x: x['relationships'][0].update(child_party_id='p3'),
    lambda x: x['facilities'][0]['lender_commitments'][0].update(lender_party_id='p1'),
    lambda x: x['interest'][0].update(facility_id='unknown'),
    lambda x: x['facilities'][0]['amount'].update(value=True),
    lambda x: x['facilities'][0]['amount'].update(value=-10),
    lambda x: x['facilities'][0]['amount'].update(status='missing'),
])
def test_invalid_facts_references_and_citations_rejected(mutate):
    value = answer(); mutate(value)
    with pytest.raises(ValueError): validate(value)


def test_parent_cycle_rejected():
    value = answer()
    value['relationships'].append({'parent_party_id': 'p1', 'child_party_id': 'p3',
        'status': 'supported', 'evidence_item_ids': ['#/texts/0']})
    with pytest.raises(ValueError, match='cycle'): validate(value)


def test_decimal_calculation_and_inconsistent_total_rejected():
    value = answer()
    rate = value['interest'][0]
    rate['calculation'] = {'kind': 'benchmark_plus_margin', 'benchmark_rate': 0.035,
        'margin_rate': 0.04, 'benchmark_floor_rate': 0.01,
        'evidence_item_ids': ['#/texts/2']}
    rate['total_rate'] = {'value': 0.075, 'status': 'supported', 'missing_inputs': []}
    assert validate(value)['interest'][0]['total_rate']['value'] == 0.075
    rate['total_rate']['value'] = 0.08
    with pytest.raises(ValueError, match='total'): validate(value)


def test_missing_calculation_input_remains_unknown():
    from credit_agreement_extractor.extraction_models import RateCalculation, calculate_total_rate
    calculation = RateCalculation(kind='benchmark_plus_margin', margin_rate=0.04,
                                  evidence_item_ids=['#/texts/2'])
    assert calculate_total_rate(calculation) is None


def test_known_statuses_and_missing_amount():
    value = answer()
    value['facilities'][0]['amount'].update(value=None, status='missing', evidence_item_ids=[])
    value['issues'] = ['Facility amount is not established in selected evidence.']
    assert validate(value)['facilities'][0]['amount']['status'] == 'missing'


def test_facility_requires_its_own_or_nested_source_evidence():
    value = answer()
    value['facilities'][0]['amount'].update(value=None, status='missing', evidence_item_ids=[])
    value['facilities'][0]['lender_commitments'] = []
    with pytest.raises(ValueError, match='Facility'): validate(value)
    value['facilities'][0]['evidence_item_ids'] = ['#/texts/1']
    assert validate(value)['facilities'][0]['amount']['value'] is None


@pytest.mark.parametrize('role', ['borrower_parent', 'lender_parent', 'parent', 'subsidiary'])
def test_corporate_relationship_is_not_an_agreement_role(role):
    value = answer(); value['parties'][2]['roles'] = [role]
    with pytest.raises(ValueError, match='role'): validate(value)


def test_uncertain_numeric_total_still_requires_consistent_arithmetic():
    value = answer(); rate = value['interest'][0]
    rate['calculation'] = {'kind': 'benchmark_plus_margin', 'benchmark_rate': 0.035,
        'margin_rate': 0.04, 'benchmark_floor_rate': 0.01,
        'evidence_item_ids': ['#/texts/2']}
    rate['total_rate'] = {'value': 0.08, 'status': 'uncertain', 'missing_inputs': []}
    value['issues'] = ['Applicability is uncertain.']
    with pytest.raises(ValueError, match='total'): validate(value)


def test_python_populates_total_from_complete_applicable_inputs():
    value = answer(); rate = value['interest'][0]
    rate['calculation'] = {'kind': 'benchmark_plus_margin', 'benchmark_rate': 0.035,
        'margin_rate': 0.04, 'benchmark_floor_rate': 0.01,
        'evidence_item_ids': ['#/texts/2']}
    rate['total_rate'] = {'value': None, 'status': 'missing', 'missing_inputs': []}
    assert validate(value)['interest'][0]['total_rate'] == {
        'value': 0.075, 'status': 'supported', 'missing_inputs': []}


def test_rate_period_and_fee_kind_are_not_lost():
    value = answer(); rate = value['interest'][0]
    rate['term_kind'] = 'fee'; rate['rate_period'] = 'one_time'
    result = validate(value)['interest'][0]
    assert result['term_kind'] == 'fee' and result['rate_period'] == 'one_time'


def test_role_case_and_spacing_are_transparently_normalized():
    value = answer(); value['parties'][1]['roles'] = [' Lender ', 'Administrative Agent']
    result = validate(value)
    assert result['parties'][1]['roles'] == ['lender', 'administrative_agent']
    assert value['parties'][1]['roles'] == [' Lender ', 'Administrative Agent']


def test_calculation_never_clears_an_unresolved_pricing_condition():
    value = answer(); rate = value['interest'][0]
    rate['calculation'] = {'kind': 'benchmark_plus_margin', 'benchmark_rate': 0.035,
        'margin_rate': 0.04, 'benchmark_floor_rate': 0.01,
        'evidence_item_ids': ['#/texts/2']}
    rate['total_rate'] = {'value': None, 'status': 'missing',
                           'missing_inputs': ['applicable_grid_row']}
    assert validate(value)['interest'][0]['total_rate'] == rate['total_rate']
