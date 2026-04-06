"""add framework column to projects

Revision ID: f8a3c91d2e05
Revises: a29004bc4c93
Create Date: 2026-04-06 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f8a3c91d2e05"
down_revision: Union[str, None] = "a29004bc4c93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type (only if it doesn't already exist)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_framework') THEN
                CREATE TYPE project_framework AS ENUM (
                    'nextjs', 'react_vite', 'remix', 'fastapi_react'
                );
            END IF;
        END
        $$;
    """)

    # Add the column (only if it doesn't already exist)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'framework'
            ) THEN
                ALTER TABLE projects ADD COLUMN framework project_framework;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS framework")
    op.execute("DROP TYPE IF EXISTS project_framework")
