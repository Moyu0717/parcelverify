"""Presentation-only guidance for the persisted review workflow."""
def guidance(case):
    """Describe the next persisted workflow state, without advancing it."""
    if case['work_bucket'] == 'resolved':
        return 3, 'Review complete', 'The recorded outcome is saved. Reopen only if new information needs checking.'
    if case.get('has_approved_actions'):
        return 1, 'Apply the approved step', 'Approval is recorded. Apply it to create the local follow-up task; approval alone does not request evidence.'
    if case.get('has_proposed_actions'):
        return 1, 'A supervisor needs to review', 'Review the request before approving it. If you cannot approve, an authorized supervisor must continue.'
    if case['work_bucket'] == 'waiting_evidence':
        return 2, 'Check the partner response', 'Open the follow-up task below. A submitted response still needs review before the case can be resolved.'
    return 0, 'Start with the evidence', 'Compare the records below. If information is missing, request a new check. If it is sufficient, review the findings and record an outcome.'
