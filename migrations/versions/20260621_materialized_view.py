"""Create materialized view for dashboard stats.

Pre-computes status breakdown and velocity per team per sprint.
Refreshed every 60s by pg_cron (non-blocking with CONCURRENTLY).
"""

from alembic import op

revision = "20260621c"
down_revision = "20260621b"


def upgrade():
    op.execute("""
        CREATE MATERIALIZED VIEW mv_team_dashboard_stats AS
        SELECT
            t.team_id,
            s.id AS sprint_id,
            s.name AS sprint_name,
            s.start_date,
            s.end_date,
            COUNT(*) FILTER (WHERE t.status = 'todo') AS todo_count,
            COUNT(*) FILTER (WHERE t.status = 'in_progress') AS in_progress_count,
            COUNT(*) FILTER (WHERE t.status = 'in_review') AS in_review_count,
            COUNT(*) FILTER (WHERE t.status = 'done') AS done_count,
            COUNT(*) FILTER (WHERE t.status = 'blocked') AS blocked_count,
            COALESCE(SUM(t.story_points) FILTER (WHERE t.status = 'done'), 0) AS completed_points,
            COALESCE(SUM(t.story_points), 0) AS total_points,
            AVG(
                EXTRACT(EPOCH FROM (t.completed_at - t.created_at)) / 3600
            ) FILTER (WHERE t.status = 'done' AND t.completed_at IS NOT NULL)
                AS avg_cycle_time_hours
        FROM tasks t
        JOIN sprints s ON t.sprint_id = s.id
        GROUP BY t.team_id, s.id, s.name, s.start_date, s.end_date
    """)

    # Required for REFRESH MATERIALIZED VIEW CONCURRENTLY
    op.execute("""
        CREATE UNIQUE INDEX ix_mv_team_dashboard_team_sprint
        ON mv_team_dashboard_stats (team_id, sprint_id)
    """)

    # Schedule refresh every 60 seconds via pg_cron
    # NOTE: pg_cron must be enabled in postgresql.conf
    op.execute("""
        SELECT cron.schedule(
            'refresh-dashboard-stats',
            '* * * * *',
            $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_team_dashboard_stats$$
        )
    """)


def downgrade():
    op.execute("SELECT cron.unschedule('refresh-dashboard-stats')")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_team_dashboard_stats")
