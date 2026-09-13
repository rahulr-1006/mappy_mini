from fastapi import APIRouter

from .. import storage

router = APIRouter(prefix="/activity-log", tags=["activity-log"])


@router.get("")
async def get_activity_log():
    return storage.get_activity_log()
