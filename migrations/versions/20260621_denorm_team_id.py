"""Denormalize team_id onto tasks table.

This avoids the tasks->sprints join in dashboard queries, which was
responsible for ~40% of query time. Yes, denormalization is a trade-off,
but for this read-heavy pattern it's worth it.

Backfill takes ~3s on 50K rows (tested on staging snapshot).
"""

from alembic import op
import sqlalchemy as sa

revision = "20260621b"
down_revision = "20260621a"


def upgrade():
    # Add the column (nullable initially for backfill)
    op.add_column("tasks", sa.Column("team_id", sa.Integer(), nullable=True))

    # Backfill from sprints table
    op.execute("""
        UPDATE tasks
        SET team_id = sprints.team_id
        FROM sprints
        WHERE tasks.sprint_id = sprints.id
    """)

    # Now make it NOT NULL
    op.alter_column("tasks", "team_id", nullable=False)

    # Add FK constraint
    op.create_foreign_key("fk_tasks_team_id", "tasks", "teams", ["team_id"], ["id"])

    # Add index for dashboard queries
    op.create_index("ix_tasks_team_id", "tasks", ["team_id"])

    # Composite index for the most common dashboard query pattern
    op.create_index("ix_tasks_team_status", "tasks", ["team_id", "status"])


def downgrade():
    op.drop_index("ix_tasks_team_status")
    op.drop_index("ix_tasks_team_id")
    op.drop_constraint("fk_tasks_team_id", "tasks")
    op.drop_column("tasks", "team_id")
