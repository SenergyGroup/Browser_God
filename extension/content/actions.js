function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function scrollToBottom({ step = 400, delay = 150, maxIterations = 100 }) {
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

    const priceContainer =
      card.querySelector(".currency-value") ||
      card.querySelector(".currency-symbol")?.parentElement ||
      card.querySelector(".n-listing-card__price") ||
      card.querySelector("[data-buy-box-listing-price]");

    const priceText = priceContainer?.textContent || priceContainer?.getAttribute("data-buy-box-listing-price");
    const price = parsePrice(priceText);

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

    if (!listingId && !link?.href) {
      return;
    }

    listings.push({
      source: "etsy",
      url: link?.href || "",
      captured_at: now,
      listing_id: listingId || (link?.href ? link.href : ""),
      title: title.trim(),
      description: "",
      price_value: price.value,
      price_currency: typeof price.currency === "string" ? price.currency : "USD",
      rating_value: ratingValue,
      rating_count: ratingCount,
      favorites: 0,
      tags: [],
      category: "",
      seller: {
        id: sellerId || "",
        name: sellerName.trim()
      },
      image_urls: imageUrls
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
  return false;
});
