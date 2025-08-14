import os
from typing import Dict, Any, Optional
import httpx

FMCSA_BASE_URL = os.getenv("FMCSA_BASE_URL", "https://mobile.fmcsa.dot.gov/qc/services")
FMCSA_API_KEY = os.getenv("FMCSA_API_KEY", "")

# Helper: safe nested get
def _g(obj: Any, *path, default=None):
    cur = obj
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

def _normalize_status(s: Optional[str]) -> str:
    return (s or "").strip().upper()

def _eligible_from_authority(authority_json: Dict[str, Any]) -> Dict[str, Any]:
    # Common/Contract/Broker authority statuses (field names used by QCMobile)
    common = _normalize_status(authority_json.get("commonAuthorityStatus"))
    contract = _normalize_status(authority_json.get("contractAuthorityStatus"))
    broker = _normalize_status(authority_json.get("brokerAuthorityStatus"))

    summary = f"Common:{common or 'N/A'}; Contract:{contract or 'N/A'}; Broker:{broker or 'N/A'}"
    any_active = any(s == "ACTIVE" for s in (common, contract, broker))
    return {"summary": summary, "any_active": any_active}

def verify_mc(mc_number: str, mock: bool = False) -> Dict[str, Any]:
    """
    Resolve MC (docket) -> DOT, then read authority + OOS.
    Returns a uniform dict used by the app.

    If mock=True: return a simulated eligible result (useful for demos when you don't want to use a real MC).
    """
    # Explicit mock for demos/tests
    if mock:
        return {
            "mc_number": mc_number,
            "eligible": True,
            "authority_status": "MOCK: Common:ACTIVE; Contract:N/A; Broker:N/A",
            "safety_rating": None,
            "source": "mock",
        }

    # If no key
    if not FMCSA_API_KEY:
        return {
            "mc_number": mc_number,
            "eligible": True,
            "authority_status": "MOCK (no FMCSA_API_KEY): Common:ACTIVE; Contract:N/A; Broker:N/A",
            "safety_rating": None,
            "source": "mock",
        }

    # QCMobile requires the key appended as ?webKey=
    params = {"webKey": FMCSA_API_KEY}

    try:
        # 1) MC (docket) -> DOT
        docket_url = f"{FMCSA_BASE_URL}/carriers/docket-number/{mc_number}"
        with httpx.Client(timeout=10.0) as client:
            r = client.get(docket_url, params=params)
            if r.status_code == 404:
                return {
                    "mc_number": mc_number,
                    "eligible": False,
                    "authority_status": "NOT FOUND",
                    "safety_rating": None,
                    "source": "fmcsa",
                }
            r.raise_for_status()
            d = r.json()

        # Extract DOT number from possible shapes
        dot_number = (
            _g(d, "content", "dotNumber")
            or _g(d, "dotNumber")
            or _g(d, "carrier", "dotNumber")
        )
        if not dot_number:
            return {
                "mc_number": mc_number,
                "eligible": False,
                "authority_status": "DOT NOT FOUND FROM DOCKET",
                "safety_rating": None,
                "source": "fmcsa",
            }

        # 2) Authority
        auth_url = f"{FMCSA_BASE_URL}/carriers/{dot_number}/authority"
        with httpx.Client(timeout=10.0) as client:
            ar = client.get(auth_url, params=params)
            ar.raise_for_status()
            a = ar.json()

        a_payload = _g(a, "content") or a
        auth_eval = _eligible_from_authority(a_payload)

        # 3) Out-of-service
        oos_active = False
        oos_url = f"{FMCSA_BASE_URL}/carriers/{dot_number}/oos"
        try:
            with httpx.Client(timeout=10.0) as client:
                orr = client.get(oos_url, params=params)
                if orr.status_code == 200:
                    o = orr.json()
                    o_content = _g(o, "content") or o
                    if isinstance(o_content, dict) and (
                        o_content.get("oosReason") or o_content.get("oosDate")
                    ):
                        oos_active = True
        except httpx.HTTPError:
            oos_active = False

        eligible = bool(auth_eval["any_active"] and not oos_active)

        return {
            "mc_number": mc_number,
            "eligible": eligible,
            "authority_status": auth_eval["summary"],
            "safety_rating": None,
            "source": "fmcsa",
        }

    except httpx.HTTPStatusError as e:
        return {
            "mc_number": mc_number,
            "eligible": False,
            "authority_status": f"HTTP {e.response.status_code}",
            "safety_rating": None,
            "source": "fmcsa",
        }
    except Exception as e:
        return {
            "mc_number": mc_number,
            "eligible": False,
            "authority_status": f"ERROR: {type(e).__name__}",
            "safety_rating": None,
            "source": "fmcsa",
        }
