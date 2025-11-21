function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function scrollToBottom({ step = 400, delay = 150, maxIterations = 100 }) {
  console.log("[Content Script] Starting scrollToBottom.");
  let lastScrollTop = -1;
  let iterations = 0;
  while (iterations < maxIterations) {
    window.scrollBy({ top: step, left: 0, behavior: "smooth" });
    await sleep(delay);
    const currentScrollTop = document.documentElement.scrollTop || document.body.scrollTop;
    if (currentScrollTop === lastScrollTop) {
      break;
    }
    lastScrollTop = currentScrollTop;
    iterations += 1;
  }
  console.log(`[Content Script] Finished scrolling after ${iterations} iterations.`);
  return { ok: true, iterations };
}

async function clickSelector({ selector, maxTimes = 1, delay = 250 }) {
  if (!selector) {
    return { ok: false, error: "MISSING_SELECTOR" };
  }
  const elements = Array.from(document.querySelectorAll(selector));
  if (!elements.length) {
    return { ok: false, error: "ELEMENT_NOT_FOUND" };
  }
  let clicks = 0;
  for (const el of elements) {
    if (clicks >= maxTimes) {
      break;
    }
    el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
    clicks += 1;
    await sleep(delay);
  }
  return { ok: true, data: { clicks } };
}

function safeParseJsonAttribute(value) {
  if (!value) {
    return null;
  }
  try {
    return JSON.parse(value);
  } catch (error) {
    try {
      return JSON.parse(value.replace(/&quot;/g, '"'));
    } catch (secondaryError) {
      console.warn("Failed to parse JSON attribute", secondaryError);
      return null;
    }
  }
}

function extractSchemas({ types = ["application/ld+json"] }) {
  if (isEtsySearchPage()) {
    return { ok: true, data: { listings: extractEtsyListings() } };
  }

  const blocks = [];
  types.forEach((type) => {
    document.querySelectorAll(`script[type="${type}"]`).forEach((node) => {
      try {
        blocks.push(JSON.parse(node.textContent));
      } catch (error) {
        console.warn("Failed to parse ld+json", error);
      }
    });
  });
  return { ok: true, data: { schemas: blocks } };
}

function isEtsySearchPage() {
  return /etsy\.com$/i.test(location.hostname) && /search/i.test(location.pathname);
}

function parsePrice(priceText) {
  if (!priceText) {
    return { value: 0, currency: "USD" };
  }
  const cleaned = priceText.replace(/\s+/g, " ").trim();
  const currencyMatch = cleaned.match(/[A-Z]{3}/);
  const currencySymbolMatch = cleaned.match(/[€$£]/);
  const symbolMap = { "€": "EUR", "$": "USD", "£": "GBP" };
  const currency = currencyMatch?.[0] || (currencySymbolMatch ? symbolMap[currencySymbolMatch[0]] : "USD");
  const numberMatch = cleaned.match(/([0-9]+(?:[.,][0-9]+)?)/);
  const rawNumber = numberMatch ? numberMatch[1] : "0";
  let normalizedNumber = rawNumber;
  if (normalizedNumber.includes(",") && !normalizedNumber.includes(".")) {
    normalizedNumber = normalizedNumber.replace(",", ".");
  } else {
    normalizedNumber = normalizedNumber.replace(/,/g, "");
  }
  const value = Number(normalizedNumber);
  return { value: Number.isFinite(value) ? value : 0, currency };
}

function parseRating(card) {
  const ratingNode =
    card.querySelector('[aria-label*="out of 5 stars" i]') ||
    card.querySelector('[data-rating]') ||
    card.querySelector(".wt-screen-reader-only");

  const ratingText = ratingNode?.getAttribute("aria-label") || ratingNode?.textContent || "";
  const ratingMatch = ratingText.match(/([0-9.]+)\s*out of 5/i);
  const ratingValue = ratingMatch ? Number(ratingMatch[1]) : null;

  const countNode =
    card.querySelector("[data-rating-count]") ||
    card.querySelector(".wt-text-caption, .wt-text-caption-small") ||
    card.querySelector("[aria-label*='reviews' i]");

  const countText = countNode?.getAttribute("data-rating-count") || countNode?.textContent || "";
  const countMatch = countText.match(/([0-9,]+)/);
  const ratingCount = countMatch ? Number(countMatch[1].replace(/,/g, "")) : null;

  return {
    ratingValue: Number.isFinite(ratingValue) ? ratingValue : null,
    ratingCount: Number.isFinite(ratingCount) ? ratingCount : null
  };
}

function extractImageUrls(card) {
  const imgs = Array.from(card.querySelectorAll("img"));
  const urls = imgs
    .map((img) => img.getAttribute("src") || img.getAttribute("data-src") || img.getAttribute("data-lazy-src"))
    .filter(Boolean);
  return Array.from(new Set(urls));
}

function extractImageAlts(card) {
  const imgs = Array.from(card.querySelectorAll("img"));
  const alts = imgs.map((img) => img.getAttribute("alt") || "").filter((alt) => alt && alt.trim().length > 0);
  return Array.from(new Set(alts));
}

function extractBadges(card) {
  const badgeCandidates = [
    ...Array.from(card.querySelectorAll("[data-badge]")),
    ...Array.from(card.querySelectorAll(".wt-badge, .listing-card-badge")),
    ...Array.from(card.querySelectorAll("[aria-label*='Free shipping' i]"))
  ];
  const badges = badgeCandidates
    .map((node) => node.textContent?.trim())
    .filter((text) => text && text.length > 0);
  return Array.from(new Set(badges));
}

function parseAppearsEventData(card) {
  const container = card.closest("[data-appears-event-data]");
  if (!container) {
    return { query: "", appearsEventData: null };
  }

  const raw = container.getAttribute("data-appears-event-data");
  const parsed = safeParseJsonAttribute(raw);
  return {
    query: parsed?.common?.query || "",
    appearsEventData: parsed
  };
}

function parseDiscount(discountText, priceValue, originalValue) {
  const discountMatch = discountText.match(/(\d+)\s*%\s*off/i);
  if (discountMatch) {
    return Number(discountMatch[1]);
  }

  if (priceValue > 0 && originalValue > priceValue) {
    const diff = originalValue - priceValue;
    return Math.round((diff / originalValue) * 100);
  }

  return null;
}

function extractPriceDetails(card) {
  const priceContainer =
    card.querySelector(".currency-value") ||
    card.querySelector(".currency-symbol")?.parentElement ||
    card.querySelector(".n-listing-card__price") ||
    card.querySelector("[data-buy-box-listing-price]");

  const priceText = priceContainer?.textContent || priceContainer?.getAttribute("data-buy-box-listing-price") || "";
  const price = parsePrice(priceText);

  const currencySymbol = card.querySelector(".currency-symbol")?.textContent?.trim() || "";

  const originalPriceNode =
    card.querySelector(".wt-text-strikethrough .currency-value") ||
    card.querySelector(".wt-text-strikethrough") ||
    card.querySelector(".search-collage-promotion-price");
  const originalPriceText = originalPriceNode?.textContent || "";
  const hasOriginal = Boolean(originalPriceText && originalPriceText.trim().length > 0);
  const originalPrice = hasOriginal ? parsePrice(originalPriceText) : { value: null, currency: null };

  const discountRegion = originalPriceNode?.parentElement || priceContainer;
  const discountPercent = parseDiscount(discountRegion?.textContent || "", price.value, originalPrice.value || 0);
  const isOnSale = Boolean(hasOriginal && originalPrice.value && price.value && originalPrice.value > price.value);

  return {
    price,
    priceText,
    currencySymbol,
    originalPriceText,
    originalPriceValue: hasOriginal ? originalPrice.value : null,
    originalPriceCurrency: hasOriginal ? originalPrice.currency : null,
    discountPercent,
    isOnSale
  };
}

function extractEtsyListings() {
  const now = new Date().toISOString();
  const cards = Array.from(
    document.querySelectorAll("li.js-merch-stash-check-listing, [data-listing-id]")
  );

  const listings = [];
  cards.forEach((card) => {
    const listingId =
      card.getAttribute("data-listing-id") ||
      card.dataset.listingId ||
      card.querySelector("[data-listing-id]")?.getAttribute("data-listing-id") ||
      (card.querySelector("a[href*='/listing/']")?.href.match(/listing\/(\d+)/) || [])[1] ||
      "";

    const link =
      card.querySelector("a.listing-link") ||
      card.querySelector("a[data-listing-id]") ||
      card.querySelector("a[href*='/listing/']");

    const title =
      card.querySelector(".v2-listing-card__title")?.textContent ||
      link?.getAttribute("title") ||
      card.querySelector("h3")?.textContent ||
      link?.textContent ||
      "";

    const priceDetails = extractPriceDetails(card);

    const { ratingValue, ratingCount } = parseRating(card);

    const sellerName =
      card.querySelector(".v2-listing-card__shop .text-body-smaller")?.textContent ||
      card.querySelector("[data-shop-name]")?.getAttribute("data-shop-name") ||
      card.querySelector("[data-shop-name]")?.textContent ||
      card.querySelector(".shop-name")?.textContent ||
      "";

    const sellerId =
      card.getAttribute("data-shop-id") ||
      card.querySelector("[data-shop-id]")?.getAttribute("data-shop-id") ||
      "";

    const imageUrls = extractImageUrls(card);
    const imageAltTexts = extractImageAlts(card);
    const thumbnailAlt = imageAltTexts[0] || link?.getAttribute("title") || title;

    const badges = extractBadges(card);

    const { query, appearsEventData } = parseAppearsEventData(card);

    const position = Number(link?.getAttribute("data-index") || card.getAttribute("data-index"));
    const loggingKey =
      link?.getAttribute("data-logging-key") ||
      card.getAttribute("data-logging-key") ||
      card.querySelector("[data-logging-key]")?.getAttribute("data-logging-key") ||
      "";

    if (!listingId && !link?.href) {
      return;
    }

    listings.push({
      source: "etsy",
      url: link?.href || "",
      captured_at: now,
      listing_id: listingId || (link?.href ? link.href : ""),
      title: title.trim(),
      description: thumbnailAlt?.trim() || "",
      price_value: priceDetails.price.value,
      price_currency: typeof priceDetails.price.currency === "string" ? priceDetails.price.currency : "USD",
      price_text: priceDetails.priceText.trim(),
      currency_symbol: priceDetails.currencySymbol || "",
      original_price_value: priceDetails.originalPriceValue,
      original_price_currency: typeof priceDetails.originalPriceCurrency === "string"
        ? priceDetails.originalPriceCurrency
        : null,
      original_price_text: priceDetails.originalPriceText.trim(),
      discount_percent: priceDetails.discountPercent,
      is_on_sale: priceDetails.isOnSale,
      rating_value: ratingValue,
      rating_count: ratingCount,
      favorites: 0,
      tags: [],
      category: "",
      seller: {
        id: sellerId || "",
        name: sellerName.trim()
      },
      image_urls: imageUrls,
      image_alt_texts: imageAltTexts,
      badges,
      search_query: query,
      appears_event_data: appearsEventData,
      position: Number.isFinite(position) ? position : null,
      logging_key: loggingKey
    });
  });

  return listings;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message?.type) {
    return;
  }
  if (message.type === "SCROLL_TO_BOTTOM") {
    scrollToBottom(message.payload || {}).then(sendResponse);
    return true;
  }
  if (message.type === "CLICK") {
    clickSelector(message.payload || {}).then(sendResponse);
    return true;
  }
  if (message.type === "EXTRACT_SCHEMA") {
    sendResponse(extractSchemas(message.payload || {}));
    return false;
  }
  if (message.type === "GET_ACTIVE_PAGE") {
    sendResponse({ ok: true, data: { activePage: detectActivePageNumber() } });
    return false;
  }
  return false;
});

function detectActivePageNumber() {
  console.log("[Content Script] Attempting to find active page number.");
  const activeButton =
    document.querySelector('[aria-current="page"], [aria-current="true"], nav[aria-label*="Pagination" i] [aria-current]') ||
    document.querySelector("[data-page][aria-current]");

  const pageText = activeButton?.textContent?.trim() || activeButton?.getAttribute("data-page") || "";
  const pageNumber = Number.parseInt(pageText, 10);
  if (Number.isFinite(pageNumber)) {
    console.log(`[Content Script] Found active page number: ${pageNumber}`);
    return pageNumber;
  }

  const fallback = document.querySelector(".wt-action-group__item button[aria-current]");
  const fallbackText = fallback?.textContent?.trim() || "";
  const fallbackNumber = Number.parseInt(fallbackText, 10);
  if (Number.isFinite(fallbackNumber)) {
    console.log(`[Content Script] Found active page number via fallback: ${fallbackNumber}`);
    return fallbackNumber;
  }

  console.log("[Content Script] Could not find an active page number.");
  return null;
}
