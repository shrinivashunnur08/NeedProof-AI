
from fastapi import APIRouter, Depends, HTTPException, Response

from app.config import get_settings
from app.services.places_service import (
    Area,
    Category,
    MerchantDiscoveryResponse,
    PlacesService,
    PlacesAPIError,
    PlacesConfigurationError,
)

router = APIRouter(
    prefix="/api/places",
    tags=["Real Merchant Discovery"],
)


def get_places_service() -> PlacesService:
    settings = get_settings()
    return PlacesService(settings.maps_api_key)


@router.get(
    "/merchants",
    response_model=MerchantDiscoveryResponse,
)
def discover_merchants(
    response: Response,
    area: Area = "Thane",
    category: Category = "electronics",
    service: PlacesService = Depends(get_places_service),
):
    settings = get_settings()

    # Chunk 4A: local development only.
    # Production exposure will require authentication
    # and request rate limiting.
    if settings.environment != "development":
        raise HTTPException(
            status_code=403,
            detail="Live discovery is not enabled in production.",
        )

    response.headers["Cache-Control"] = "no-store"

    try:
        return service.search(area, category)

    except PlacesConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except PlacesAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
