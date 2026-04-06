from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import AI_LOOP_REPORTS_DIR
from app.services.ai_chat.loop_service import LOOP_LOCK, LOOP_SESSIONS, loop_report_payload

router = APIRouter()


@router.get("/loop/{loop_id}/report")
async def loop_report(loop_id: str):
    return loop_report_payload(loop_id)


@router.get("/loop/{loop_id}/report/download")
async def loop_report_download(loop_id: str):
    with LOOP_LOCK:
        session = LOOP_SESSIONS.get(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Loop not found")
        md_path = Path(session.get("md_report_path") or (AI_LOOP_REPORTS_DIR / f"{loop_id}.md"))
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(
        path=str(md_path),
        media_type="text/markdown",
        filename=f"{loop_id}.md",
    )
