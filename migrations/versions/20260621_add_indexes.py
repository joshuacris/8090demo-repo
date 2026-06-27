"""Add composite indexes for dashboard queries.

The existing single-column indexes on sprint_id and status weren't being
used by the join queries. Composite indexes match the actual query patterns.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260621a"
down_revision = "20260615a"


def upgrade():
    op.create_index(
        "ix_tasks_sprint_status",
        "tasks",
        ["sprint_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_tasks_sprint_assignee",
        "tasks",
        ["sprint_id", "assignee_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_tasks_sprint_assignee")
    op.drop_index("ix_tasks_sprint_status")
