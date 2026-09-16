"""Finite benign service conditions, created before observation and classification.

This module creates only local synthetic administrative conditions. It cannot
modify a COMMON document or invoke a treatment, scorer, model, or external host.
"""
from copy import deepcopy

SEED_CONDITIONS = ('acceptance_absent','acceptance_wrong_scope','ingress_expired','parent_version')
CLEAN_CONDITIONS = ('clean_direct','clean_delegated')
CONTROL_CONDITIONS = ('coherent_false',)
CONDITIONS = SEED_CONDITIONS + CLEAN_CONDITIONS + CONTROL_CONDITIONS


def active_fault(condition, node, attempt, world_index):
    if condition not in CONDITIONS or type(attempt) is not int or attempt not in (0,1):
        raise ValueError('Unregistered condition or attempt')
    if node != 'R1' or condition not in SEED_CONDITIONS:
        return None
    # Single initial seed. Service availability is a prospective world property.
    if attempt == 1 and world_index % 2 == 0:
        return None
    return condition


def declaration_response(records, fault, attempt, prior_records=None):
    """Record the service's actual response; preserve earlier declarations.

    A node-scoped source ledger contains every declaration issued for that node.
    A refresh with unchanged, applicable declarations reuses them. On correction
    of scope or absence, the service issues a new version and lists that version
    as the requested use's basis; old records remain in the complete history.
    """
    current = deepcopy(records)
    if fault == 'acceptance_absent':
        current['declarations'] = [r for r in current['declarations'] if r['declaration_kind'] != 'ADOPTION_DECLARED']
        current['included_refs'] = [r['declaration_version_ref'] for r in current['declarations']]
        current['declared_basis_refs'] = []
    elif fault == 'acceptance_wrong_scope':
        for row in current['declarations']:
            if row['declaration_kind'] == 'ADOPTION_DECLARED':
                row['scope_id'] = 'SCOPE_OTHER'
    if not attempt or prior_records is None:
        return current
    prior = deepcopy(prior_records)
    prior_basis = [r for r in prior['declarations'] if r['declaration_version_ref'] in prior['declared_basis_refs']]
    if fault in ('acceptance_absent','acceptance_wrong_scope'):
        return prior
    if prior_basis and all(r.get('scope_id') == 'SCOPE_SYNTHETIC' for r in prior_basis):
        return prior
    # The only remaining registered case is an available administrative repair.
    new_acceptance = next(r for r in current['declarations'] if r['declaration_kind']=='ADOPTION_DECLARED')
    new_acceptance['declaration_version_ref'] = 'DECL_USE_REFRESH_1'
    prior['declarations'].append(new_acceptance)
    prior['included_refs'].append(new_acceptance['declaration_version_ref'])
    prior['declared_basis_refs'] = [new_acceptance['declaration_version_ref']]
    return prior
