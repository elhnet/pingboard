"""Tests for the database layer — pruning logic."""

import pytest

import db as db_module


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    db_module.init_db(db_path)
    return db_path


def test_prune_keeps_200_checks(tmp_db):
    """Insert >200 checks for a URL, prune, verify only 200 remain."""
    url_id = db_module.add_url("https://example.com", db_path=tmp_db)

    for i in range(250):
        db_module.record_check(url_id, status_code=200, response_time_ms=float(i), db_path=tmp_db)

    # Verify all 250 exist before prune
    all_checks = db_module.get_latest_checks(url_id, n=300, db_path=tmp_db)
    assert len(all_checks) == 250

    # Prune to 200
    deleted = db_module.prune_old_checks(keep=200, db_path=tmp_db)
    assert deleted == 50

    # Verify only 200 remain
    remaining = db_module.get_latest_checks(url_id, n=300, db_path=tmp_db)
    assert len(remaining) == 200


def test_prune_per_url(tmp_db):
    """Pruning keeps 200 per URL, not 200 total."""
    url_a = db_module.add_url("https://a.example.com", db_path=tmp_db)
    url_b = db_module.add_url("https://b.example.com", db_path=tmp_db)

    for i in range(210):
        db_module.record_check(url_a, status_code=200, response_time_ms=float(i), db_path=tmp_db)
        db_module.record_check(url_b, status_code=200, response_time_ms=float(i), db_path=tmp_db)

    db_module.prune_old_checks(keep=200, db_path=tmp_db)

    remaining_a = db_module.get_latest_checks(url_a, n=300, db_path=tmp_db)
    remaining_b = db_module.get_latest_checks(url_b, n=300, db_path=tmp_db)
    assert len(remaining_a) == 200
    assert len(remaining_b) == 200
