export function validateListingRecord(record) {
  if (!record || typeof record !== "object") {
    return false;
  }
  const requiredStringFields = ["source", "url", "listing_id", "title", "price_currency"];
  for (const field of requiredStringFields) {
    if (!record[field] || typeof record[field] !== "string") {
      return false;
    }
  }
  if (typeof record.price_value !== "number") {
    return false;
  }
  if (typeof record.rating_value !== "number" && record.rating_value !== null && record.rating_value !== undefined) {
    return false;
  }
  if (typeof record.rating_count !== "number" && record.rating_count !== null && record.rating_count !== undefined) {
    return false;
  }
  if (!Array.isArray(record.tags)) {
    return false;
  }
  if (!Array.isArray(record.image_urls)) {
    return false;
  }
  return true;
}

export function validateReviewRecord(record) {
  if (!record || typeof record !== "object") {
    return false;
  }
  const requiredStringFields = ["source", "listing_id", "review_id", "author_slug", "text"];
  for (const field of requiredStringFields) {
    if (!record[field] || typeof record[field] !== "string") {
      return false;
    }
  }
  if (typeof record.rating_value !== "number") {
    return false;
  }
  if (typeof record.created_utc !== "number") {
    return false;
  }
  return true;
}
