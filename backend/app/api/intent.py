
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.schemas.intent import (
    IntentRequest,
    IntentAnalysisResponse,
)
from app.services.intent_service import (
    IntentService,
    IntentConfigurationError,
    IntentModelError,
    IntentOutputError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intent", tags=["AI Intent"])


def get_intent_service() -> IntentService:
    return IntentService(get_settings())


@router.post(
    "/extract",
    response_model=IntentAnalysisResponse,
)
def extract_customer_intent(
    payload: IntentRequest,
    service: IntentService = Depends(get_intent_service),
):
    try:
        return service.extract(payload.text)

    except IntentConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except IntentOutputError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except IntentModelError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
