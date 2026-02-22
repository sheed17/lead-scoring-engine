"""
Single LLM call for structured extraction from dental practice website text.

Input: homepage text, services page text, pricing page text (optional).
Output: Strict JSON schema — service_focus, pricing, operations, positioning.
Temperature 0, minimal max tokens. No other reasoning.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 45
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are a structured data extractor for dental practice websites.

Your ONLY job is to output valid JSON. No markdown, no explanation, no other text.
Use the exact schema below. All booleans must be true/false. All numbers must be numbers or null.

Schema (output this and nothing else):
{
  "service_focus": {
    "implants": {"mentioned": false, "emphasized": false},
    "invisalign": {"mentioned": false, "emphasized": false},
    "veneers": {"mentioned": false, "emphasized": false},
    "emergency": {"mentioned": false, "emphasized": false}
  },
  "pricing": {
    "new_patient_special": false,
    "explicit_prices_found": [],
    "financing_detected": false
  },
  "operations": {
    "staff_count_estimate": {"value": null, "confidence": 0.0},
    "multiple_locations": false
  },
  "positioning": {
    "premium": false,
    "insurance_heavy": false
  }
}

- mentioned: service is clearly mentioned on the site.
- emphasized: featured as a main offering (dedicated section, CTA, or headline).
- new_patient_special: new patient offer, discount, or free exam mentioned.
- explicit_prices_found: list of price strings if any are shown (e.g. "$99 new patient").
- financing_detected: payment plans, CareCredit, or financing mentioned.
- staff_count_estimate.value: integer or null if not stated; confidence 0-1.
- multiple_locations: more than one office/location mentioned.
- premium: language suggests premium/cosmetic/luxury positioning.
- insurance_heavy: emphasizes insurance acceptance, in-network, etc."""

USER_PROMPT_TEMPLATE = """Extract structured data from the following dental practice website text.
Return ONLY valid JSON matching the schema. No markdown code blocks, no other text.

--- HOMEPAGE ---
{homepage_text}

--- SERVICES PAGE (if any) ---
{services_text}

--- PRICING PAGE (if any) ---
{pricing_text}
"""


def _get_client():
    try:
        from openai import OpenAI
        return OpenAI()
    except ImportError:
        return None


def _default_schema() -> Dict[str, Any]:
    return {
        "service_focus": {
            "implants": {"mentioned": False, "emphasized": False},
            "invisalign": {"mentioned": False, "emphasized": False},
            "veneers": {"mentioned": False, "emphasized": False},
            "emergency": {"mentioned": False, "emphasized": False},
        },
        "pricing": {
            "new_patient_special": False,
            "explicit_prices_found": [],
            "financing_detected": False,
        },
        "operations": {
            "staff_count_estimate": {"value": None, "confidence": 0.0},
            "multiple_locations": False,
        },
        "positioning": {
            "premium": False,
            "insurance_heavy": False,
        },
    }


def _normalize_extraction(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure response matches schema types."""
    default = _default_schema()
    out = {}
    for key in ("service_focus", "pricing", "operations", "positioning"):
        if key not in data or not isinstance(data[key], dict):
            out[key] = default[key]
            continue
        blob = data[key]
        if key == "service_focus":
            out[key] = {}
            for sk in ("implants", "invisalign", "veneers", "emergency"):
                v = blob.get(sk) if isinstance(blob.get(sk), dict) else {}
                out[key][sk] = {
                    "mentioned": bool(v.get("mentioned")),
                    "emphasized": bool(v.get("emphasized")),
                }
        elif key == "pricing":
            out[key] = {
                "new_patient_special": bool(blob.get("new_patient_special")),
                "explicit_prices_found": [str(x) for x in (blob.get("explicit_prices_found") or []) if x][:10],
                "financing_detected": bool(blob.get("financing_detected")),
            }
        elif key == "operations":
            est = blob.get("staff_count_estimate")
            if isinstance(est, dict):
                val = est.get("value")
                conf = est.get("confidence")
            else:
                val, conf = None, 0.0
            if isinstance(val, (int, float)) and val >= 0:
                val = int(val)
            else:
                val = None
            if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
                conf = 0.0
            out[key] = {
                "staff_count_estimate": {"value": val, "confidence": round(float(conf), 2)},
                "multiple_locations": bool(blob.get("multiple_locations")),
            }
        elif key == "positioning":
            out[key] = {
                "premium": bool(blob.get("premium")),
                "insurance_heavy": bool(blob.get("insurance_heavy")),
            }
        else:
            out[key] = default[key]
    return out


def extract_structured(
    homepage_text: str,
    services_page_text: Optional[str] = None,
    pricing_page_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Single LLM call: extract structured JSON from website text.
    Temperature 0, minimal max tokens. Returns default schema on failure.
    """
    if not (homepage_text or "").strip():
        return _default_schema()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.debug("OPENAI_API_KEY not set; returning default schema")
        return _default_schema()

    client = _get_client()
    if not client:
        logger.debug("OpenAI client not available; returning default schema")
        return _default_schema()

    user = USER_PROMPT_TEMPLATE.format(
        homepage_text=(homepage_text or "")[:8000],
        services_text=(services_page_text or "").strip()[:6000] or "(none provided)",
        pricing_text=(pricing_page_text or "").strip()[:4000] or "(none provided)",
    )

    try:
        model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            temperature=0,
            max_tokens=MAX_TOKENS,
            timeout=REQUEST_TIMEOUT,
        )
        text = (r.choices[0].message.content or "").strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        data = json.loads(text)
        return _normalize_extraction(data)
    except (json.JSONDecodeError, TypeError, KeyError, IndexError) as e:
        logger.warning("LLM structured extraction parse error: %s", e)
        return _default_schema()
    except Exception as e:
        logger.warning("LLM structured extraction request failed: %s", e)
        return _default_schema()
