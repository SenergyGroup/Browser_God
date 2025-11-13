function safeGet(obj, path, fallback = null) {
  return path.split(".").reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : null), obj) ?? fallback;
}

function randomId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function normalizePrice(listing) {
  const price = listing.price || listing.price_amount || safeGet(listing, "price.amount");
  const currency = listing.currency || safeGet(listing, "price.currency_code") || safeGet(listing, "price.currency");
  return {
    value: typeof price === "number" ? price : Number(price?.amount || price?.value || price) || 0,
    currency: typeof currency === "string" ? currency : "USD"
  };
}

export function transformEtsyListing(payload, sourceUrl) {
  if (!payload) {
    return [];
  }
  const listings = [];
  const items = Array.isArray(payload.results) ? payload.results : Array.isArray(payload.listings) ? payload.listings : [payload];
  for (const item of items) {
    const price = normalizePrice(item);
    const listingId = `${item.listing_id || item.listingId || item.id || "unknown"}`;
    const ratingValue = Number(safeGet(item, "rating.rating") || safeGet(item, "rating.average") || item.average_rating || item.rating) || null;
    const ratingCount = Number(safeGet(item, "rating.count") || item.rating_count || item.reviews_count) || null;
    listings.push({
      source: "etsy",
      url: sourceUrl,
      captured_at: new Date().toISOString(),
      listing_id: listingId,
      title: item.title || item.name || "",
      description: item.description || "",
      price_value: price.value,
      price_currency: price.currency,
      rating_value: ratingValue,
      rating_count: ratingCount,
      favorites: Number(item.num_favorers || item.favorites || 0),
      tags: Array.isArray(item.tags) ? item.tags : [],
      category: item.category_path?.join(" > ") || item.category || "",
      seller: {
        id: `${safeGet(item, "Shop.shop_id") || safeGet(item, "shop.shop_id") || safeGet(item, "shop_id") || ""}`,
        name: safeGet(item, "Shop.shop_name") || safeGet(item, "shop.shop_name") || safeGet(item, "shop_name") || ""
      },
      image_urls: Array.isArray(item.Images)
        ? item.Images.map((img) => img.url_fullxfull || img.url_570xN).filter(Boolean)
        : Array.isArray(item.images)
        ? item.images.map((img) => img.url || img.src).filter(Boolean)
        : []
    });
  }
  return listings;
}

export function transformEtsyReviews(payload) {
  if (!payload) {
    return [];
  }
  const records = [];
  const reviews = Array.isArray(payload.results) ? payload.results : Array.isArray(payload.reviews) ? payload.reviews : [];
  for (const review of reviews) {
    records.push({
      source: "etsy",
      listing_id: `${review.listing_id || review.listingId || ""}`,
      review_id: `${review.transaction_id || review.review_id || review.id || randomId()}`,
      rating_value: Number(review.rating || review.value || 0),
      created_utc: Number(review.created_timestamp || review.create_timestamp || review.created) || Math.floor(Date.now() / 1000),
      author_slug: review.login_name || review.author || review.reviewer || "",
      text: review.review || review.message || review.body || ""
    });
  }
  return records;
}
