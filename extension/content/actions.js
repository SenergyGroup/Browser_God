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
