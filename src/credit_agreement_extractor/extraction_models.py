"""Stage D's data contract and deterministic checks, independent of any LLM.

Schema validation proves shape, not legal truth. Citation checks prove that a
source item was supplied, not that it logically establishes the model's claim.
Keep these boundaries explicit when evaluating extraction quality.
"""
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def _number(value):
    # JSON true is not the number 1; numeric strings are deliberately rejected.
    if type(value) not in (int, float):
        raise ValueError('Expected a JSON number, not a string or boolean.')
    return value


Number = Annotated[float, BeforeValidator(_number), Field(ge=0, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=1, pattern=r'\S')]
FactStatus = Literal['supported', 'missing', 'uncertain', 'not_applicable']


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class CitedRecord(StrictRecord):
    evidence_item_ids: list[Text]


class PartyRecord(CitedRecord):
    party_id: Text
    name: Text
    roles: list[Text]
    status: Literal['supported', 'uncertain']


class RelationshipRecord(CitedRecord):
    # Parent/child is corporate structure, separate from agreement roles.
    parent_party_id: Text
    child_party_id: Text
    status: Literal['supported', 'uncertain']


class AmountRecord(CitedRecord):
    value: Number | None
    kind: Literal['commitment', 'principal', 'outstanding', 'original', 'amended']
    status: FactStatus

    @model_validator(mode='after')
    def consistent_status(self):
        if self.status == 'supported' and (self.value is None or not self.evidence_item_ids):
            raise ValueError('Supported amount requires a numeric value and evidence.')
        if self.status in ('missing', 'not_applicable') and self.value is not None:
            raise ValueError('Missing/not-applicable amount cannot have a value.')
        return self


class LenderCommitment(CitedRecord):
    lender_party_id: Text
    amount: Number
    status: Literal['supported', 'uncertain']


class FacilityRecord(StrictRecord):
    facility_id: Text
    type: Text | None
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')] | None
    amount: AmountRecord
    lender_commitments: list[LenderCommitment]
    # An amount may be unknown even though the facility itself is established.
    # Existing amount/commitment citations also support the initial record shape.
    evidence_item_ids: list[Text] = Field(default_factory=list)


class TotalRate(StrictRecord):
    value: Number | None
    status: Literal['supported', 'missing', 'uncertain', 'not_applicable', 'missing_inputs']
    missing_inputs: list[Text]

    @model_validator(mode='after')
    def consistent_status(self):
        if self.status == 'supported' and (self.value is None or self.missing_inputs):
            raise ValueError('Supported total needs a number and no missing inputs.')
        if self.status in ('missing', 'not_applicable', 'missing_inputs') and self.value is not None:
            raise ValueError('Unavailable total must not have a number.')
        if self.status == 'missing_inputs' and not self.missing_inputs:
            raise ValueError('Identify missing total-rate inputs explicitly.')
        return self


class RateCalculation(CitedRecord):
    # This typed record is the ONLY executable rate rule. Never eval formula.
    kind: Literal['fixed', 'benchmark_plus_margin']
    fixed_rate: Number | None = None
    benchmark_rate: Number | None = None
    margin_rate: Number | None = None
    benchmark_floor_rate: Number | None = None

    @model_validator(mode='after')
    def one_rule(self):
        if self.kind == 'fixed' and any(x is not None for x in
            (self.benchmark_rate, self.margin_rate, self.benchmark_floor_rate)):
            raise ValueError('Fixed calculation cannot include floating-rate inputs.')
        if self.kind == 'benchmark_plus_margin' and self.fixed_rate is not None:
            raise ValueError('Floating calculation cannot include a fixed rate.')
        return self


class InterestRecord(CitedRecord):
    facility_id: Text
    term_kind: Literal['interest', 'fee'] = 'interest'
    # 1.5% monthly must not silently become 1.5% annually. Preserve the stated
    # period without annualizing or confusing a one-time fee with loan interest.
    rate_period: Text | None = None
    rate_type: Literal['fixed', 'floating', 'mixed', 'unknown']
    benchmark: Text | None
    margin_rate: Number | None
    benchmark_floor_rate: Number | None
    formula: Text | None
    total_rate: TotalRate
    payment_frequency: Text | None
    day_count: Text | None
    # Keep contractual conditions/PIK/grid language without pretending it is a
    # resolved numeric rate. The structured rule only covers the simple cases.
    conditions: Text | None = None
    pik_terms: Text | None = None
    calculation: RateCalculation | None = None


class CreditTerms(StrictRecord):
    """Model-facing sections only; Python supplies identity/completion metadata."""
    parties: list[PartyRecord]
    relationships: list[RelationshipRecord]
    facilities: list[FacilityRecord]
    interest: list[InterestRecord]
    issues: list[Text]


def calculate_total_rate(calculation: RateCalculation) -> float | None:
    """Calculate only known, typed inputs using exact decimal arithmetic."""
    if calculation.kind == 'fixed':
        return calculation.fixed_rate
    if calculation.benchmark_rate is None or calculation.margin_rate is None:
        return None
    base = Decimal(str(calculation.benchmark_rate))
    if calculation.benchmark_floor_rate is not None:
        base = max(base, Decimal(str(calculation.benchmark_floor_rate)))
    return float(base + Decimal(str(calculation.margin_rate)))


def validate_extraction(payload: dict, allowed_ids: set[str]) -> dict:
    """Validate facts, references and rate consistency without mutating input."""
    result = CreditTerms.model_validate(payload)

    def citations(record, *, required=True):
        ids = record.evidence_item_ids
        if (required and not ids) or len(ids) != len(set(ids)) or not set(ids) <= allowed_ids:
            raise ValueError('Evidence citations must be unique supplied source item IDs.')

    parties = {p.party_id: p for p in result.parties}
    names = {p.name.strip().casefold() for p in result.parties}
    if len(parties) != len(result.parties) or len(names) != len(result.parties):
        raise ValueError('Duplicate party ID/name; use one entity with multiple roles.')
    for party in result.parties:
        citations(party)
        # Roles are labels, not legal names. Preserve names/source wording but
        # normalize "Lender" and " lender " to the same machine-readable role.
        party.roles = ['_'.join(role.strip().casefold().split()) for role in party.roles]
        if len(party.roles) != len(set(party.roles)):
            raise ValueError('Duplicate agreement roles.')
        if any(role.strip().casefold().replace(' ', '_') in
               {'borrower_parent', 'lender_parent', 'parent', 'child', 'subsidiary', 'holding_company'}
               for role in party.roles):
            raise ValueError('Corporate parent-child relationships are not agreement roles.')

    children = {p: [] for p in parties}
    seen_links = set()
    for link in result.relationships:
        citations(link)
        pair = (link.parent_party_id, link.child_party_id)
        if (not set(pair) <= parties.keys() or pair[0] == pair[1] or pair in seen_links):
            raise ValueError('Invalid or duplicate parent-child reference.')
        children[pair[0]].append(pair[1]); seen_links.add(pair)
    # Iterative traversal avoids recursion failures on large corporate chains.
    for start in children:
        stack = [(start, frozenset())]
        while stack:
            node, ancestors = stack.pop()
            if node in ancestors:
                raise ValueError('Parent-child cycle detected.')
            stack.extend((child, ancestors | {node}) for child in children[node])

    facilities = {f.facility_id: f for f in result.facilities}
    if len(facilities) != len(result.facilities):
        raise ValueError('Duplicate facility ID.')
    for facility in result.facilities:
        citations(facility, required=False)
        citations(facility.amount, required=facility.amount.status not in ('missing',))
        if not (facility.evidence_item_ids or facility.amount.evidence_item_ids
                or facility.lender_commitments):
            raise ValueError('Facility identity requires supplied source evidence.')
        for commitment in facility.lender_commitments:
            citations(commitment)
            lender = parties.get(commitment.lender_party_id)
            if lender is None or 'lender' not in lender.roles:
                raise ValueError('Lender commitment must reference an identified lender.')

    for interest in result.interest:
        citations(interest)
        if interest.facility_id not in facilities:
            raise ValueError('Interest references an unknown facility.')
        calculation = interest.calculation
        if calculation is not None:
            citations(calculation)
            if ((calculation.kind == 'fixed' and interest.rate_type != 'fixed') or
                (calculation.kind == 'benchmark_plus_margin' and interest.rate_type != 'floating')):
                raise ValueError('Calculation kind and interest rate type disagree.')
            for key in ('margin_rate', 'benchmark_floor_rate'):
                if getattr(calculation, key) != getattr(interest, key):
                    raise ValueError('Calculation inputs differ from extracted interest terms.')
            computed = calculate_total_rate(calculation)
            if interest.total_rate.value is not None:
                if computed is None or Decimal(str(interest.total_rate.value)) != Decimal(str(computed)):
                    raise ValueError('Numeric total does not match deterministic calculation.')
            elif (computed is not None and interest.total_rate.status == 'missing'
                  and not interest.total_rate.missing_inputs):
                # Complete, cited applicable inputs can yield a total even when
                # the model did not do the arithmetic. Never override uncertainty.
                interest.total_rate = TotalRate(value=computed, status='supported', missing_inputs=[])
        elif interest.total_rate.value is not None:
            raise ValueError('Numeric total requires a typed calculation with applicability evidence.')
    return result.model_dump(mode='json')
