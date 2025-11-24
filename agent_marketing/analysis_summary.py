"""Generate structured product briefs from an analysis summary."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import httpx

from dotenv import load_dotenv

load_dotenv() 

# Defaults relative to project root
DEFAULT_SUMMARY_PATH = Path("data_streams/analysis/analysis_summary.json")
DEFAULT_OUTPUT_DIR = Path("data_streams/products")

# Example brief schema for validation
BRIEF_TEMPLATE = {
    "keyword": "twitch chat overlay cyberpunk",
    "product_type": "chat overlay pack",
    "style_notes": ["neon", "dark background", "readable fonts"],
    "file_types": ["PNG"],
    "components": ["chat box", "alerts"],
    "target_price": 12.99,
    "differentiation_points": [
        "mobile friendly layout",
        "stream safe fonts",
    ],
}


def load_summary(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Summary file not found at {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_prompts(summary: Dict[str, Any]) -> Dict[str, str]:
    topic_name = summary.get("topic_name", "unknown topic")

    system_prompt = (
        "You are a market research and product design assistant for digital streaming assets.\n"
        "You receive a JSON market snapshot for a single Etsy topic and must propose concrete "
        "digital products that could be sold as overlays, widgets, alerts, or graphic packs.\n\n"
        "Constraints:\n"
        "- Only propose digital products (no physical items, printing, or services).\n"
        "- Products must be realistic for a solo creator to build using graphics and HTML/CSS/JS.\n"
        "- Use the pricing and competition information in the snapshot to choose competitive but "
        "profitable prices.\n"
        "- Use language and keywords that match what buyers type on Etsy.\n"
    )

    user_prompt = (
        "Market snapshot JSON:\n\n"
        f"{json.dumps(summary, indent=2)}\n\n"
        "Task:\n"
        f"- The topic for this snapshot is: {topic_name!r}.\n"
        "- Propose exactly 3 concrete product ideas as Etsy listing concepts.\n"
        "- Each product must be returned as a JSON object with the following keys:\n"
        "  - keyword: string, an Etsy search phrase buyers would use.\n"
        "  - product_type: string, such as 'chat overlay pack', 'alert widget', 'stream panel set'.\n"
        "  - style_notes: array of short strings describing visual style.\n"
        "  - file_types: array of file type strings, such as 'PNG', 'WEBM', 'HTML', 'CSS', 'JS'.\n"
        "  - components: array of components included in the product, such as 'chat box', "
        "    'alerts', 'starting soon screen', 'offline screen'.\n"
        "  - target_price: number, the recommended price in the same currency as the snapshot.\n"
        "  - differentiation_points: array of short strings describing how this product stands out.\n\n"
        "Output format:\n"
        "- Respond with a single JSON object with one key 'briefs'.\n"
        "- The value of 'briefs' must be an array of exactly 3 product brief objects.\n"
        "- Do not include any extra keys or text outside this JSON object.\n\n"
        "Example shape (do not reuse exactly):\n"
        "{\n"
        "  \"briefs\": [\n"
        "    {\n"
        "      \"keyword\": \"twitch chat overlay cyberpunk\",\n"
        "      \"product_type\": \"chat overlay pack\",\n"
        "      \"style_notes\": [\"neon\", \"dark background\", \"readable fonts\"],\n"
        "      \"file_types\": [\"PNG\"],\n"
        "      \"components\": [\"chat box\", \"alerts\"],\n"
        "      \"target_price\": 12.99,\n"
        "      \"differentiation_points\": [\n"
        "        \"mobile friendly layout\",\n"
        "        \"stream safe fonts\"\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )

    return {"system": system_prompt, "user": user_prompt}


def compact_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce summary size so the prompt is cheaper and easier for small models."""
    compact = dict(summary)  # shallow copy

    # Limit example listings
    examples = summary.get("top_example_listings", [])
    trimmed_examples = []
    for row in examples[:8]:  # keep only first 8
        trimmed_examples.append({
            "listing_id": row.get("listing_id"),
            "title": row.get("title"),
            "price": row.get("price"),
            "favorites": row.get("favorites"),
            "rating_count": row.get("rating_count"),
            "is_code": row.get("is_code"),
            "is_bestseller": row.get("is_bestseller"),
            "seller_name": row.get("seller_name"),
            # URLs and images are long and not essential for this step
            "tags": row.get("tags", []),
        })

    compact["top_example_listings"] = trimmed_examples

    # Optionally limit keywords too
    keywords = summary.get("top_keywords_expensive", [])
    compact["top_keywords_expensive"] = keywords[:10]

    return compact



def call_openai_for_briefs(
    summary: Dict[str, Any],
    brief_count: int = 3,
) -> List[Dict[str, Any]]:
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    prompts = build_prompts(summary)

    request_payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 1,
        "max_completion_tokens": 8192,
    }

    # Debug: show what we are sending
    print("\n--- OpenAI request payload ---")
    print(json.dumps(request_payload, indent=2))
    print("--- end request payload ---\n")

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=request_payload,
        timeout=45,
    )
    response.raise_for_status()

    full = response.json()

    # Debug: show raw response
    print("\n--- OpenAI raw response ---")
    print(json.dumps(full, indent=2))
    print("--- end raw response ---\n")

    choice = (full.get("choices") or [{}])[0]
    message = choice.get("message") or {}

    # Newer APIs sometimes return content as a list of segments
    raw_content = message.get("content", "")

    if isinstance(raw_content, list):
        # e.g. [{ "type": "output_text", "text": "..."}, ...]
        content = "".join(
            part.get("text", "")
            for part in raw_content
            if isinstance(part, dict) and "text" in part
        )
    elif isinstance(raw_content, str):
        content = raw_content
    else:
        content = ""

    if not content or not content.strip():
        raise ValueError(
            "Model returned empty content. Check the printed raw response above "
            "to see how the data is structured."
        )

    # Strip common code-fence wrappers ```json ... ```
    stripped = content.strip()
    if stripped.startswith("```"):
        # remove leading ```[json] and trailing ```
        stripped = stripped.strip("`")
        # in case it starts with 'json'
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].lstrip()

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        # Extra debug to help see what failed
        print("\n--- content that failed to parse ---")
        print(stripped)
        print("--- end content ---\n")
        raise ValueError(f"Model response was not valid JSON: {exc}") from exc

    # Accept either {"briefs": [...]} or a raw list
    if isinstance(data, dict):
        briefs = data.get("briefs", [])
    elif isinstance(data, list):
        briefs = data
    else:
        raise ValueError("Unexpected JSON structure from model")

    if not isinstance(briefs, list):
        raise ValueError("Expected 'briefs' to be a list")

    if len(briefs) != brief_count:
        raise ValueError(f"Expected {brief_count} briefs, got {len(briefs)}")

    for idx, brief in enumerate(briefs):
        if not isinstance(brief, dict):
            raise ValueError(f"Brief {idx} is not an object")
        for key in BRIEF_TEMPLATE.keys():
            if key not in brief:
                raise ValueError(f"Brief {idx} missing key '{key}'")

    return briefs



def save_briefs(briefs: List[Dict[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "product_briefs.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(briefs, f, indent=2)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate product briefs from analysis_summary.json using OpenAI"
    )
    parser.add_argument(
        "--summary-path",
        type=str,
        default=str(DEFAULT_SUMMARY_PATH),
        help="Path to analysis_summary.json",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to write product_briefs.json",
    )
    parser.add_argument(
        "--brief-count",
        type=int,
        default=3,
        help="Number of briefs to request and validate",
    )
    args = parser.parse_args()

    summary_path = Path(args.summary_path)
    output_dir = Path(args.output_dir)

    summary = load_summary(summary_path)
    summary = compact_summary(summary)
    briefs = call_openai_for_briefs(summary, brief_count=args.brief_count)
    output_path = save_briefs(briefs, output_dir)

    print(f"Wrote {len(briefs)} product briefs to {output_path}")


if __name__ == "__main__":
    main()
