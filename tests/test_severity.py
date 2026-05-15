"""Severity contract: the canonical vocabulary is enforced in one place."""

from backend.config import SEVERITY_ACTION_THRESHOLD, SEVERITY_LEVELS


CANONICAL = ("low", "medium", "high", "critical")


def test_canonical_vocabulary():
    assert tuple(SEVERITY_LEVELS) == CANONICAL


def test_action_threshold_is_a_subset_of_canonical():
    for level in SEVERITY_ACTION_THRESHOLD:
        assert level in SEVERITY_LEVELS


def test_no_legacy_terms_in_threshold():
    # "urgent" and "moderate" used to leak through actions.py + sf_news.py.
    for legacy in ("urgent", "moderate", "improving"):
        assert legacy not in SEVERITY_LEVELS
        assert legacy not in SEVERITY_ACTION_THRESHOLD
