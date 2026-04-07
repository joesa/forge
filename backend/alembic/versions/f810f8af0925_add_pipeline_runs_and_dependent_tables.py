"""add_pipeline_runs_and_dependent_tables

Revision ID: f810f8af0925
Revises: c7f2b84a910e
Create Date: 2026-04-06 23:10:00.000000

Adds all tables that exist in ORM models but were missing from the DB:
pipeline_runs, ai_providers, idea_sessions, chat_messages, preview_shares,
sandboxes, agent_outputs, builds, editor_sessions, accessibility_reports,
annotations, build_snapshots, coherence_reports, deployments, hot_fix_records,
performance_reports, seed_data_records.

Does NOT alter or drop any existing production tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f810f8af0925'
down_revision: Union[str, None] = 'c7f2b84a910e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# PostgreSQL native enum types to create
pipeline_status = sa.Enum(
    'queued', 'running', 'completed', 'failed', 'cancelled',
    name='pipeline_status',
)
build_status = sa.Enum(
    'pending', 'building', 'succeeded', 'failed',
    name='build_status',
)
sandbox_status = sa.Enum(
    'warming', 'ready', 'assigned', 'terminating', 'terminated',
    name='sandbox_status',
)
agent_name_enum = sa.Enum(
    'prd', 'design_system', 'layout', 'component', 'page', 'api',
    'state', 'integration', 'config', 'quality',
    name='agent_name_enum',
)
agent_output_status = sa.Enum(
    'pending', 'running', 'completed', 'failed',
    name='agent_output_status',
)
coherence_status = sa.Enum(
    'pending', 'passed', 'failed', 'fixed',
    name='coherence_status',
)
deployment_status = sa.Enum(
    'pending', 'deploying', 'live', 'failed', 'rolled_back',
    name='deployment_status',
)
deployment_target = sa.Enum(
    'cloudflare_pages', 'northflank', 'vercel',
    name='deployment_target',
)
hot_fix_status = sa.Enum(
    'pending', 'applied', 'failed', 'reverted',
    name='hot_fix_status',
)
provider_name_enum = sa.Enum(
    'anthropic', 'openai', 'gemini', 'grok', 'mistral',
    'cohere', 'deepseek', 'together',
    name='provider_name_enum',
)
idea_session_status = sa.Enum(
    'active', 'completed', 'abandoned',
    name='idea_session_status',
)
chat_role = sa.Enum(
    'user', 'assistant', 'system',
    name='chat_role',
)


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Tables with no foreign-key dependencies on new tables               #
    # ------------------------------------------------------------------ #

    op.create_table(
        'ai_providers',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('provider_name', provider_name_enum, nullable=False),
        sa.Column('encrypted_key', sa.LargeBinary(), nullable=False),
        sa.Column('key_iv', sa.LargeBinary(), nullable=False),
        sa.Column('key_tag', sa.LargeBinary(), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_connected', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_providers_user_id', 'ai_providers', ['user_id'], unique=False)
    op.create_index('uq_user_provider', 'ai_providers', ['user_id', 'provider_name'], unique=True)

    op.create_table(
        'idea_sessions',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=True),
        sa.Column('initial_prompt', sa.Text(), nullable=True),
        sa.Column('status', idea_session_status, server_default=sa.text("'active'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_idea_sessions_user_id', 'idea_sessions', ['user_id'], unique=False)
    op.create_index('ix_idea_sessions_user_status', 'idea_sessions', ['user_id', 'status'], unique=False)

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role', chat_role, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_project_id', 'chat_messages', ['project_id'], unique=False)
    op.create_index('ix_chat_messages_user_id', 'chat_messages', ['user_id'], unique=False)
    op.create_index('ix_chat_messages_user_status', 'chat_messages', ['user_id', 'role'], unique=False)

    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('status', pipeline_status, server_default=sa.text("'queued'"), nullable=False),
        sa.Column('current_stage', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pipeline_runs_project_id', 'pipeline_runs', ['project_id'], unique=False)
    op.create_index('ix_pipeline_runs_user_id', 'pipeline_runs', ['user_id'], unique=False)
    op.create_index('ix_pipeline_runs_user_status', 'pipeline_runs', ['user_id', 'status'], unique=False)

    op.create_table(
        'preview_shares',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('share_token', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('share_token'),
    )
    op.create_index('ix_preview_shares_project_id', 'preview_shares', ['project_id'], unique=False)
    op.create_index('ix_preview_shares_share_token', 'preview_shares', ['share_token'], unique=True)
    op.create_index('ix_preview_shares_user_id', 'preview_shares', ['user_id'], unique=False)

    op.create_table(
        'sandboxes',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('status', sandbox_status, server_default=sa.text("'warming'"), nullable=False),
        sa.Column('vm_id', sa.String(length=256), nullable=True),
        sa.Column('vm_url', sa.String(length=2048), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sandboxes_project_id', 'sandboxes', ['project_id'], unique=False)
    op.create_index('ix_sandboxes_status', 'sandboxes', ['status'], unique=False)
    op.create_index('ix_sandboxes_user_id', 'sandboxes', ['user_id'], unique=False)
    op.create_index('ix_sandboxes_user_status', 'sandboxes', ['user_id', 'status'], unique=False)

    # ------------------------------------------------------------------ #
    # Tables that depend on pipeline_runs                                  #
    # ------------------------------------------------------------------ #

    op.create_table(
        'agent_outputs',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('pipeline_run_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('agent_name', agent_name_enum, nullable=False),
        sa.Column('stage', sa.Integer(), nullable=False),
        sa.Column('status', agent_output_status, server_default=sa.text("'pending'"), nullable=False),
        sa.Column('output_text', sa.Text(), nullable=True),
        sa.Column('output_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['pipeline_run_id'], ['pipeline_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_outputs_pipeline_run_id', 'agent_outputs', ['pipeline_run_id'], unique=False)
    op.create_index('ix_agent_outputs_user_id', 'agent_outputs', ['user_id'], unique=False)
    op.create_index('ix_agent_outputs_user_status', 'agent_outputs', ['user_id', 'status'], unique=False)

    op.create_table(
        'builds',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('pipeline_run_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('status', build_status, server_default=sa.text("'pending'"), nullable=False),
        sa.Column('build_number', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('commit_sha', sa.String(length=64), nullable=True),
        sa.Column('gate_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('log_url', sa.String(length=2048), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['pipeline_run_id'], ['pipeline_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_builds_pipeline_run_id', 'builds', ['pipeline_run_id'], unique=False)
    op.create_index('ix_builds_project_id', 'builds', ['project_id'], unique=False)
    op.create_index('ix_builds_user_id', 'builds', ['user_id'], unique=False)
    op.create_index('ix_builds_user_status', 'builds', ['user_id', 'status'], unique=False)

    # ------------------------------------------------------------------ #
    # Tables that depend on sandboxes                                      #
    # ------------------------------------------------------------------ #

    op.create_table(
        'editor_sessions',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('sandbox_id', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('last_file_path', sa.String(length=1024), nullable=True),
        sa.Column('open_tabs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sandbox_id'], ['sandboxes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_editor_sessions_project_id', 'editor_sessions', ['project_id'], unique=False)
    op.create_index('ix_editor_sessions_sandbox_id', 'editor_sessions', ['sandbox_id'], unique=False)
    op.create_index('ix_editor_sessions_user_id', 'editor_sessions', ['user_id'], unique=False)
    op.create_index('ix_editor_sessions_user_status', 'editor_sessions', ['user_id', 'is_active'], unique=False)

    # ------------------------------------------------------------------ #
    # Tables that depend on builds                                         #
    # ------------------------------------------------------------------ #

    op.create_table(
        'accessibility_reports',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('build_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('route', sa.String(length=512), nullable=False),
        sa.Column('violations', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('warnings', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('passes', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('critical_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('passed_gate', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_accessibility_reports_build_id', 'accessibility_reports', ['build_id'], unique=False)
    op.create_index('ix_accessibility_reports_project_id', 'accessibility_reports', ['project_id'], unique=False)

    op.create_table(
        'annotations',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('build_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('x_pct', sa.Float(), nullable=False),
        sa.Column('y_pct', sa.Float(), nullable=False),
        sa.Column('page_route', sa.String(length=512), nullable=True),
        sa.Column('css_selector', sa.String(length=1024), nullable=True),
        sa.Column('session_id', sa.String(length=256), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('resolved', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_annotations_build_id', 'annotations', ['build_id'], unique=False)
    op.create_index('ix_annotations_project_id', 'annotations', ['project_id'], unique=False)
    op.create_index('ix_annotations_project_resolved', 'annotations', ['project_id', 'resolved'], unique=False)
    op.create_index('ix_annotations_user_id', 'annotations', ['user_id'], unique=False)

    op.create_table(
        'build_snapshots',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('build_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('snapshot_index', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=256), nullable=True),
        sa.Column('file_tree', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('screenshot_url', sa.String(length=2048), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_build_snapshots_build_id', 'build_snapshots', ['build_id'], unique=False)
    op.create_index('ix_build_snapshots_project_id', 'build_snapshots', ['project_id'], unique=False)

    op.create_table(
        'coherence_reports',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('build_id', sa.String(), nullable=False),
        sa.Column('pipeline_run_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('status', coherence_status, server_default=sa.text("'pending'"), nullable=False),
        sa.Column('issues_found', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('issues_fixed', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('all_passed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pipeline_run_id'], ['pipeline_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_coherence_reports_build_id', 'coherence_reports', ['build_id'], unique=False)
    op.create_index('ix_coherence_reports_pipeline_run_id', 'coherence_reports', ['pipeline_run_id'], unique=False)
    op.create_index('ix_coherence_reports_project_id', 'coherence_reports', ['project_id'], unique=False)
    op.create_index('ix_coherence_reports_user_id', 'coherence_reports', ['user_id'], unique=False)
    op.create_index('ix_coherence_reports_user_status', 'coherence_reports', ['user_id', 'status'], unique=False)

    op.create_table(
        'deployments',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('build_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('status', deployment_status, server_default=sa.text("'pending'"), nullable=False),
        sa.Column('target', deployment_target, nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=True),
        sa.Column('commit_sha', sa.String(length=64), nullable=True),
        sa.Column('deploy_log', sa.Text(), nullable=True),
        sa.Column('environment', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_deployments_build_id', 'deployments', ['build_id'], unique=False)
    op.create_index('ix_deployments_project_id', 'deployments', ['project_id'], unique=False)
    op.create_index('ix_deployments_user_id', 'deployments', ['user_id'], unique=False)
    op.create_index('ix_deployments_user_status', 'deployments', ['user_id', 'status'], unique=False)

    op.create_table(
        'hot_fix_records',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('build_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('status', hot_fix_status, server_default=sa.text("'pending'"), nullable=False),
        sa.Column('attempt_number', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('error_input', sa.Text(), nullable=True),
        sa.Column('fix_description', sa.Text(), nullable=True),
        sa.Column('files_changed', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_hot_fix_records_build_id', 'hot_fix_records', ['build_id'], unique=False)
    op.create_index('ix_hot_fix_records_project_id', 'hot_fix_records', ['project_id'], unique=False)
    op.create_index('ix_hot_fix_records_user_id', 'hot_fix_records', ['user_id'], unique=False)
    op.create_index('ix_hot_fix_records_user_status', 'hot_fix_records', ['user_id', 'status'], unique=False)

    op.create_table(
        'performance_reports',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('build_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('route', sa.String(length=512), nullable=False),
        sa.Column('lcp_ms', sa.Float(), nullable=True),
        sa.Column('cls_score', sa.Float(), nullable=True),
        sa.Column('fid_ms', sa.Float(), nullable=True),
        sa.Column('ttfb_ms', sa.Float(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_performance_reports_build_id', 'performance_reports', ['build_id'], unique=False)
    op.create_index('ix_performance_reports_project_id', 'performance_reports', ['project_id'], unique=False)
    op.create_index('ix_performance_reports_user_id', 'performance_reports', ['user_id'], unique=False)

    op.create_table(
        'seed_data_records',
        sa.Column('id', sa.String(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('build_id', sa.String(), nullable=True),
        sa.Column('tables_seeded', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('total_rows', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('seed_schema', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_seed_data_records_build_id', 'seed_data_records', ['build_id'], unique=False)
    op.create_index('ix_seed_data_records_project_id', 'seed_data_records', ['project_id'], unique=False)


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('seed_data_records')
    op.drop_table('performance_reports')
    op.drop_table('hot_fix_records')
    op.drop_table('deployments')
    op.drop_table('coherence_reports')
    op.drop_table('build_snapshots')
    op.drop_table('annotations')
    op.drop_table('accessibility_reports')
    op.drop_table('editor_sessions')
    op.drop_table('builds')
    op.drop_table('agent_outputs')
    op.drop_table('sandboxes')
    op.drop_table('preview_shares')
    op.drop_table('pipeline_runs')
    op.drop_table('chat_messages')
    op.drop_table('idea_sessions')
    op.drop_table('ai_providers')

    # Drop enum types
    pipeline_status.drop(op.get_bind(), checkfirst=True)
    build_status.drop(op.get_bind(), checkfirst=True)
    sandbox_status.drop(op.get_bind(), checkfirst=True)
    agent_name_enum.drop(op.get_bind(), checkfirst=True)
    agent_output_status.drop(op.get_bind(), checkfirst=True)
    coherence_status.drop(op.get_bind(), checkfirst=True)
    deployment_status.drop(op.get_bind(), checkfirst=True)
    deployment_target.drop(op.get_bind(), checkfirst=True)
    hot_fix_status.drop(op.get_bind(), checkfirst=True)
    provider_name_enum.drop(op.get_bind(), checkfirst=True)
    idea_session_status.drop(op.get_bind(), checkfirst=True)
    chat_role.drop(op.get_bind(), checkfirst=True)
