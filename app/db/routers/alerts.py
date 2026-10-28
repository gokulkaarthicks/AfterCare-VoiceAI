"""Alert endpoints for the care-team dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import alerts as alerts_repo
from app.shared.database.engine import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    severity: str | None = Query(default=None),
    acknowledged: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await alerts_repo.list_alerts(
        session, severity=severity, acknowledged=acknowledged
    )


@router.patch("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    alert = await alerts_repo.acknowledge_alert(session, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"id": alert.id, "acknowledged": alert.acknowledged}
