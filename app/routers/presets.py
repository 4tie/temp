from fastapi import APIRouter, HTTPException

from app.schemas.backtest import PresetSaveRequest
from app.services.storage import load_presets, save_preset, delete_preset

router = APIRouter(prefix="/presets", tags=["presets"])


@router.get("")
async def get_presets():
    presets = load_presets()
    return {"presets": presets}


@router.post("")
async def create_preset(req: PresetSaveRequest):
    save_preset(req.name, req.config)
    return {"saved": True, "name": req.name}


@router.delete("/{name}")
async def remove_preset(name: str):
    deleted = delete_preset(name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"deleted": True}
