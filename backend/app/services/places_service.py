
import logging
from typing import Literal

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

# Request only the fields needed for merchant discovery.
FIELD_MASK = (
    "places.id,"
    "places.displayName.text,"
    "places.formattedAddress,"
    "places.googleMapsUri"
)

Area = Literal[
    "Thane",
    "Dombivli",
    "Kalyan",
    "Badlapur",
    "Navi Mumbai",
    "Mumbai",
]

Category = Literal["electronics", "computer", "mobile"]

CATEGORY_QUERIES = {
    "electronics": "electronics stores",
    "computer": "computer and laptop shops",
    "mobile": "mobile phone stores",
}


class PlacesConfigurationError(Exception):
    pass


class PlacesAPIError(Exception):
    pass


class LiveMerchant(BaseModel):
    place_id: str
    name: str
    address: str
    maps_url: str | None = None

    source: Literal["GOOGLE_PLACES"] = "GOOGLE_PLACES"
    is_simulated: bool = False

    stock_status: Literal["UNKNOWN"] = "UNKNOWN"
    price_status: Literal["UNKNOWN"] = "UNKNOWN"
    compatibility_status: Literal["UNKNOWN"] = "UNKNOWN"


class MerchantDiscoveryResponse(BaseModel):
    mode: Literal["LIVE_DISCOVERY"] = "LIVE_DISCOVERY"
    area: str
    category: str
    merchants: list[LiveMerchant] = Field(default_factory=list)

    notice: str = (
        "Business identities come from Google Maps Platform. "
        "Product inventory, prices, and compatibility are unknown."
    )


class PlacesService:
    def __init__(
        self,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
    ):
        self.api_key = api_key
        self.transport = transport

    def search(
        self,
        area: Area,
        category: Category,
    ) -> MerchantDiscoveryResponse:
        if not self.api_key.strip():
            raise PlacesConfigurationError(
                "MAPS_API_KEY is not configured."
            )

        query = (
            f"{CATEGORY_QUERIES[category]} "
            f"in {area}, Maharashtra, India"
        )

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        payload = {
            "textQuery": query,
            "pageSize": 6,
            "languageCode": "en",
            "regionCode": "IN",
        }

        try:
            with httpx.Client(
                timeout=15.0,
                transport=self.transport,
            ) as client:
                response = client.post(
                    PLACES_URL,
                    headers=headers,
                    json=payload,
                )

                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Places API returned HTTP %s",
                exc.response.status_code,
            )
            raise PlacesAPIError(
                f"Google Places returned HTTP "
                f"{exc.response.status_code}. "
                "Check API access, billing, key restrictions, "
                "and quota."
            ) from exc

        except (httpx.RequestError, ValueError) as exc:
            logger.error(
                "Places API request or response failed: %s",
                type(exc).__name__,
            )
            raise PlacesAPIError(
                "Google Places could not be reached "
                "or returned invalid data."
            ) from exc

        merchants = []

        for place in data.get("places", []):
            place_id = place.get("id")
            name = place.get("displayName", {}).get("text")

            if not place_id or not name:
                continue

            maps_url = place.get("googleMapsUri")

            # Only use secure links returned by Google.
            if not (
                isinstance(maps_url, str)
                and maps_url.startswith("https://")
            ):
                maps_url = None

            merchants.append(
                LiveMerchant(
                    place_id=place_id,
                    name=name,
                    address=place.get(
                        "formattedAddress",
                        "Address unavailable",
                    ),
                    maps_url=maps_url,
                )
            )

        return MerchantDiscoveryResponse(
            area=area,
            category=category,
            merchants=merchants,
        )
