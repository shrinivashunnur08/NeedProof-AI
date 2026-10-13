export type JourneyArea =
  | "Thane"
  | "Dombivli"
  | "Kalyan"
  | "Badlapur"
  | "Navi Mumbai"
  | "Mumbai";

export type JourneyCategory = "electronics" | "computer" | "mobile";

export interface JourneyPrefill {
  area: JourneyArea | null;
  category: JourneyCategory;
  productQuery: string;
}

export interface JourneyMerchant {
  place_id: string;
  name: string;
  address: string;
  maps_url: string | null;
}

export interface JourneyDiscovery {
  area: string;
  category: string;
  product_query: string;
  merchants: JourneyMerchant[];
  fetched_at: string;
}

export interface JourneyEvidence {
  place_id: string;
  request_id: number;
  product_query: string;
  status: string;

  submission: {
    product_name: string;
    stock_quantity: number;
    price_minor: number | null;
    currency: string;
    delivery_available: boolean | null;
    submitted_at: string | null;
  } | null;

  assessment: {
    status: string;
    freshness: string;
    reported_fields: number;
    total_fields: number;
    eligible_for_commitment: boolean;
    recommended_next_action: {
      code: string;
      label: string;
    };
  } | null;

  updated_at: string;
}

export function makeJourneyPrefill(intent: {
  requested_product: string;
  product_category: string | null;
  delivery_location: string | null;
}): JourneyPrefill {
  const location = (intent.delivery_location ?? "").toLowerCase();

  const areas: JourneyArea[] = [
    "Navi Mumbai",
    "Dombivli",
    "Badlapur",
    "Kalyan",
    "Thane",
    "Mumbai",
  ];

  // These are suggestions based on extracted text,
  // not arbitrary Google Places address geocoding.
  const area =
    areas.find((value) => location.includes(value.toLowerCase())) ?? null;

  const description = (
    intent.requested_product +
    " " +
    (intent.product_category ?? "")
  ).toLowerCase();

  let category: JourneyCategory = "electronics";

  if (/laptop|notebook|computer|macbook|usb-c pd/.test(description)) {
    category = "computer";
  } else if (/mobile|smartphone|iphone|android/.test(description)) {
    category = "mobile";
  }

  return {
    area,
    category,
    productQuery: intent.requested_product.trim().slice(0, 250),
  };
}
