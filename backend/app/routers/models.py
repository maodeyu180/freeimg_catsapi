from fastapi import APIRouter

from app.model_config import get_public_model_list

router = APIRouter()


@router.get("")
async def list_models():
    return {"items": get_public_model_list()}
