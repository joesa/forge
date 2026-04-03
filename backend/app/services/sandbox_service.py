"""
Sandbox service — lifecycle management for Firecracker VMs.

Handles: claim, start, stop, destroy, command execution.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sandbox import Sandbox, SandboxStatus

logger = structlog.get_logger()


async def create_sandbox(
    project_id: str,
    user_id: str,
    session: AsyncSession,
) -> Sandbox:
    """Claim a sandbox from the pre-warmed pool (SELECT FOR UPDATE SKIP LOCKED)."""
    # In production: claim from pool with row-level lock
    sandbox = Sandbox(
        project_id=uuid.UUID(project_id),
        user_id=uuid.UUID(user_id),
        status=SandboxStatus.assigned,
    )
    session.add(sandbox)
    await session.flush()

    logger.info("sandbox_created", sandbox_id=str(sandbox.id), project_id=project_id)
    return sandbox


async def get_sandbox(
    sandbox_id: str,
    user_id: str,
    session: AsyncSession,
) -> Sandbox:
    """Get a sandbox by ID with ownership check."""
    stmt = select(Sandbox).where(
        Sandbox.id == uuid.UUID(sandbox_id),
        Sandbox.user_id == uuid.UUID(user_id),
    )
    result = await session.execute(stmt)
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise LookupError(f"Sandbox {sandbox_id} not found or access denied")
    return sandbox


async def stop_sandbox(
    sandbox_id: str,
    user_id: str,
    session: AsyncSession,
) -> Sandbox:
    """Stop a running sandbox (begin termination)."""
    sandbox = await get_sandbox(sandbox_id, user_id, session)

    await session.execute(
        sa_update(Sandbox)
        .where(Sandbox.id == sandbox.id)
        .values(status=SandboxStatus.terminating)
    )
    await session.flush()

    logger.info("sandbox_stopped", sandbox_id=sandbox_id)
    return sandbox


async def destroy_sandbox(
    sandbox_id: str,
    user_id: str,
    session: AsyncSession,
) -> None:
    """Destroy a sandbox and release resources."""
    sandbox = await get_sandbox(sandbox_id, user_id, session)

    await session.execute(
        sa_update(Sandbox)
        .where(Sandbox.id == sandbox.id)
        .values(status=SandboxStatus.terminated)
    )
    await session.flush()

    logger.info("sandbox_destroyed", sandbox_id=sandbox_id)


async def execute_command(
    sandbox_id: str,
    user_id: str,
    command: str,
    session: AsyncSession,
) -> str:
    """Execute a command in a sandbox and return the output."""
    await get_sandbox(sandbox_id, user_id, session)

    # In production: send command to sandbox via internal API
    logger.info("sandbox_command", sandbox_id=sandbox_id, command=command)
    return f"Command '{command}' queued for sandbox {sandbox_id}"
