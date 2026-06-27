"""Regression tests for dashboard query performance."""
import pytest
from sqlalchemy import text


def test_status_query_uses_index(db_session):
    """Verify the composite index is used for status breakdown."""
    result = db_session.execute(text("""
        EXPLAIN (FORMAT JSON)
        SELECT status, count(*)
        FROM tasks
        WHERE team_id = 1
        GROUP BY status
    """))
    plan = result.fetchone()[0]
    plan_text = str(plan)
    assert "Index Scan" in plan_text or "Index Only Scan" in plan_text


def test_materialized_view_exists(db_session):
    """Verify the materialized view was created."""
    result = db_session.execute(text("""
        SELECT count(*) FROM pg_matviews
        WHERE matviewname = 'mv_team_dashboard_stats'
    """))
    assert result.scalar() == 1


def test_team_id_denorm_in_sync(db_session):
    """Verify denormalized team_id matches sprint.team_id for all tasks."""
    result = db_session.execute(text("""
        SELECT count(*) FROM tasks t
        JOIN sprints s ON t.sprint_id = s.id
        WHERE t.team_id != s.team_id
    """))
    assert result.scalar() == 0, "Denormalized team_id out of sync!"
