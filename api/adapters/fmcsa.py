# api/adapters/fmcsa.py
import os
import re
import json
from typing import Dict, Any, Optional, Tuple
import httpx

FMCSA_BASE_URL = os.getenv("FMCSA_BASE_URL", "https://mobile.fmcsa.dot.gov/qc/services")
FMCSA_API_KEY = os.getenv("FMCSA_API_KEY", "")

_HDRS = {"Accept": "application/json", "User-Agent": "happyrobot-inbound/1.0"}

# ---------- helpers ----------
def _normalize_mc(mc: str) -> str:
    """Keep digits only (strip 'MC', spaces, dashes)."""
    return re.sub(r"\D", "", mc or "")

def _find_dot(obj: Any) -> Optional[str]:
    """Recursively find dotNumber anywhere in dict/list payloads."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        if obj.get("dotNumber"):
            return str(obj["dotNumber"])
        for v in obj.values():
            x = _find_dot(v)
            if x:
                return x
    elif isinstance(obj, list):
        for it in obj:
            x = _find_dot(it)
            if x:
                return x
    return None

def _coerce_mapping(x: Any) -> Dict[str, Any]:
    """Return a dict view for either a dict or the first dict found in a list; else {}."""
    if isinstance(x, dict):
        return x
    if isinstance(x, list):
        for it in x:
            if isinstance(it, dict):
                return it
    return {}

def _status_is_active(s: Optional[str]) -> bool:
    """Normalize authority codes/words to boolean active."""
    s = (s or "").strip().upper()
    return s in {"A", "ACTIVE", "Y", "YES", "AUTHORIZED"}

def _label(s: Optional[str]) -> str:
    """Pretty labels for summary strings."""
    m = {"A": "ACTIVE", "I": "INACTIVE", "N": "NONE", "Y": "ACTIVE"}
    up = (s or "").strip().upper()
    return m.get(up, up or "N/A")

def _maybe_debug(label: str, obj: Any):
    if os.getenv("FMCSA_DEBUG"):
        try:
            print(f"[FMCSA DEBUG] {label}: {obj if isinstance(obj, str) else json.dumps(obj)[:500]}")
        except Exception:
            pass

def _extract_statuses_recursive(obj: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Recursively hunt for keys that look like common/contract/broker authority status.
    Supports shapes like:
      {"commonAuthorityStatus":"A"}
      {"commonAuthority":{"status":"A"}}
      {"common":{"authorityStatus":"A"}}
    Returns (common, contract, broker), values may be None if not found.
    """
    common = contract = broker = None

    def visit(x: Any):
        nonlocal common, contract, broker
        if isinstance(x, dict):
            for k, v in x.items():
                k_low = k.lower()
                # If value is dict with 'status', drill into it
                def val2(vv):
                    if isinstance(vv, dict):
                        # consider 'status' or 'value'
                        return vv.get("status") or vv.get("value")
                    return vv
                if "commonauthority" in k_low or ("common" in k_low and "authority" in k_low):
                    if common is None:
                        common = val2(v)
                elif "contractauthority" in k_low or ("contract" in k_low and "authority" in k_low):
                    if contract is None:
                        contract = val2(v)
                elif "brokerauthority" in k_low or ("broker" in k_low and "authority" in k_low):
                    if broker is None:
                        broker = val2(v)
                # Recurse
                visit(v)
        elif isinstance(x, list):
            for it in x:
                visit(it)

    visit(obj)
    def as_str(v):
        return v if isinstance(v, str) else None
    return as_str(common), as_str(contract), as_str(broker)

def _eligible_from_authority(authority_json: Any, docket_fallback: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Compute any_active + summary from authority payload,
    falling back to values we saw on the docket payload if authority is missing them.
    """
    # extract recursively
    c_raw, ct_raw, b_raw = _extract_statuses_recursive(authority_json)

    # Fallback to docket fields if still missing
    if docket_fallback:
        c_raw = c_raw or docket_fallback.get("commonAuthorityStatus")
        ct_raw = ct_raw or docket_fallback.get("contractAuthorityStatus")
        b_raw = b_raw or docket_fallback.get("brokerAuthorityStatus")

    any_active = any(_status_is_active(x) for x in (c_raw, ct_raw, b_raw))
    summary = f"Common:{_label(c_raw)}; Contract:{_label(ct_raw)}; Broker:{_label(b_raw)}"
    return {"summary": summary, "any_active": any_active}

# ---------- main ----------
def verify_mc(mc_number: str, mock: bool = False) -> Dict[str, Any]:
    """
    Resolve MC (docket) -> DOT, then read authority + OOS.
    Returns:
      { mc_number, eligible, authority_status, safety_rating, source, dot_number?, legal_name? }

    If mock=True OR no FMCSA_API_KEY: return a simulated eligible result.
    """
    if mock or not FMCSA_API_KEY:
        return {
            "mc_number": mc_number,
            "eligible": True,
            "authority_status": "MOCK: Common:ACTIVE; Contract:N/A; Broker:N/A",
            "safety_rating": None,
            "source": "mock",
        }

    mc_digits = _normalize_mc(mc_number)
    params = {"webKey": FMCSA_API_KEY}

    try:
        with httpx.Client(timeout=10.0, headers=_HDRS) as client:
            # 1) MC (docket) -> DOT
            r = client.get(f"{FMCSA_BASE_URL}/carriers/docket-number/{mc_digits}", params=params)
            notfound = (r.status_code == 404) or (
                r.status_code == 200 and isinstance(r.json().get("content"), list) and len(r.json()["content"]) == 0
            )
            if notfound:
                r = client.get(f"{FMCSA_BASE_URL}/carriers/search/docket-number/{mc_digits}", params=params)
            r.raise_for_status()
            d = r.json()
            _maybe_debug("docket_raw", d)

            content = d.get("content", d)
            dot_number = _find_dot(content)
            if not dot_number:
                return {
                    "mc_number": mc_number,
                    "eligible": False,
                    "authority_status": "DOT NOT FOUND FROM DOCKET",
                    "safety_rating": None,
                    "source": "fmcsa",
                }

            # Enrich from docket
            legal_name = None
            oos_date_present = False
            docket_statuses = {}
            try:
                first = content[0] if isinstance(content, list) and content else content
                carrier = first.get("carrier", {}) if isinstance(first, dict) else {}
                legal_name = carrier.get("legalName")
                oos_date_present = bool(carrier.get("oosDate"))
                # potential status codes from docket
                docket_statuses = {
                    "commonAuthorityStatus": carrier.get("commonAuthorityStatus"),
                    "contractAuthorityStatus": carrier.get("contractAuthorityStatus"),
                    "brokerAuthorityStatus": carrier.get("brokerAuthorityStatus"),
                }
            except Exception:
                pass

            # 2) Authority
            ar = client.get(f"{FMCSA_BASE_URL}/carriers/{dot_number}/authority", params=params)
            ar.raise_for_status()
            a = ar.json()
            _maybe_debug("authority_raw", a)
            a_payload = a.get("content", a)
            auth_eval = _eligible_from_authority(a_payload, docket_fallback=docket_statuses)

            # 3) Out-of-service
            oos_active = False
            try:
                orr = client.get(f"{FMCSA_BASE_URL}/carriers/{dot_number}/oos", params=params)
                if orr.status_code == 200:
                    o = orr.json()
                    _maybe_debug("oos_raw", o)
                    oc = o.get("content", o)
                    if isinstance(oc, dict):
                        if oc.get("oosReason") or oc.get("oosDate"):
                            oos_active = True
                    elif isinstance(oc, list):
                        for it in oc:
                            if isinstance(it, dict) and (it.get("oosReason") or it.get("oosDate")):
                                oos_active = True
                                break
            except httpx.HTTPError:
                pass  # non-blocking

            eligible = bool(auth_eval["any_active"] and not (oos_active or oos_date_present))

            return {
                "mc_number": mc_number,
                "eligible": eligible,
                "authority_status": auth_eval["summary"],
                "safety_rating": None,
                "source": "fmcsa",
                "dot_number": str(dot_number),
                "legal_name": legal_name,
            }

    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text[:200]
        except Exception:
            pass
        return {
            "mc_number": mc_number,
            "eligible": False,
            "authority_status": f"HTTP {e.response.status_code} {body}",
            "safety_rating": None,
            "source": "fmcsa",
        }
    except Exception as e:
        return {
            "mc_number": mc_number,
            "eligible": False,
            "authority_status": f"ERROR: {type(e).__name__}: {str(e)[:160]}",
            "safety_rating": None,
            "source": "fmcsa",
        }
