"""fix missing column defaults and add missing user columns

Revision ID: c7f2b84a910e
Revises: f8a3c91d2e05
Create Date: 2026-04-06 00:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7f2b84a910e"
down_revision: Union[str, None] = "f8a3c91d2e05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── projects: add missing server defaults ───────────────────────
    op.execute("ALTER TABLE projects ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute("ALTER TABLE projects ALTER COLUMN design_mode_locked SET DEFAULT false")
    op.execute("ALTER TABLE projects ALTER COLUMN created_at SET DEFAULT now()")
    op.execute("ALTER TABLE projects ALTER COLUMN updated_at SET DEFAULT now()")

    # ── users: add missing columns ──────────────────────────────────
    op.execute("ALTER TABLE users ALTER COLUMN created_at SET DEFAULT now()")

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='users' AND column_name='avatar_url') THEN
                ALTER TABLE users ADD COLUMN avatar_url VARCHAR(2048);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='users' AND column_name='onboarded') THEN
                ALTER TABLE users ADD COLUMN onboarded BOOLEAN NOT NULL DEFAULT false;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'plan_tier') THEN
                CREATE TYPE plan_tier AS ENUM ('free', 'pro', 'enterprise');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='users' AND column_name='plan') THEN
                ALTER TABLE users ADD COLUMN plan plan_tier NOT NULL DEFAULT 'free';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='users' AND column_name='token_limit_monthly') THEN
                ALTER TABLE users ADD COLUMN token_limit_monthly INTEGER NOT NULL DEFAULT 2000000;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='users' AND column_name='updated_at') THEN
                ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT now();
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE projects ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE projects ALTER COLUMN design_mode_locked DROP DEFAULT")
    op.execute("ALTER TABLE projects ALTER COLUMN created_at DROP DEFAULT")
    op.execute("ALTER TABLE projects ALTER COLUMN updated_at DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN created_at DROP DEFAULT")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_url")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS onboarded")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS plan")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS token_limit_monthly")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS updated_at")
