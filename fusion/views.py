from __future__ import annotations

import json
import time
import re
import traceback
from typing import Any, Dict, Optional, List

import requests
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt

# ===================== Constantes API SF =====================
API_BASE = "https://api.servicefusion.com"
API_VERSION = "v1"
TOKEN_URL = f"{API_BASE}/oauth/access_token"

# ----------------- Catégories autorisées + mapping UI -> SF -----------------
ALLOWED_CATEGORIES = {
    "Building Controls",
    "Cold side",
    "Electrical",
    "Hot side",
    "HVAC",
    "Preventative Maintenance Cooking Equipment",
    "Preventative Maintenance HVAC",
    "Preventative Maintenance HVAC-R",
    "Preventative Maintenance Refrigeration",
    "Warranty",
}
CATEGORY_MAP = {
    "Refrigeration": "Cold side",
    "Plumbing": "Hot side",
    "Electrical": "Electrical",
    "HVAC": "HVAC",
    "General Maintenance": "Warranty",
}

# ----------------- Statuts autorisés -----------------
ALLOWED_STATUSES = [
    "Cancelled", "Completed", "Delayed", "Dispatched", "Needs Estimate",
    "On Site", "On The Way", "Partially Completed", "Parts Ordered",
    "Paused", "Picking up parts", "Resumed", "Scheduled",
    "Started", "Unscheduled",
]
STATUS_DEFAULT = "Unscheduled"

# ----------------- Technicien par défaut -----------------
DEFAULT_TECHNICIAN = {
    "id": 980629768,  # ID réel du technicien "AnswringAgent AfterHours" dans Service Fusion
    "first_name": "AnswringAgent",
    "last_name": "AfterHours"
}

# ===================== Cache runtime =====================
_OAUTH_CACHE: Dict[str, Any] = {"access_token": None, "exp": 0}

# ===================== Pages =====================
# Removed legacy views (home/connect/mapping) during cleanup; only core pages remain

# ===================== Utils =====================
def _timeout() -> int:
    return int(getattr(settings, "HTTP_TIMEOUT", 30))


def home(request: HttpRequest):
    return render(request, "bluecollar_website_connected.html", {})
def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _safe_get(d: Dict[str, Any] | None, *keys, default=None):
    cur = d or {}
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def _json_error(e: Exception, path: str, resp: Optional[requests.Response] = None) -> JsonResponse:
    detail = {"error": "Service Fusion error", "path": path, "message": str(e)}
    if resp is not None:
        detail["status_code"] = resp.status_code
        try:
            j = resp.json()
            if isinstance(j, list):
                msgs = []
                for it in j:
                    if isinstance(it, dict):
                        msg = it.get("message") or it.get("error_description") or it.get("error")
                        if msg: msgs.append(msg)
                detail["response"] = " | ".join(msgs) if msgs else j
            else:
                detail["response"] = j
        except Exception:
            detail["response"] = resp.text
    print("SF ERROR:", json.dumps(detail, ensure_ascii=False))
    traceback.print_exc()
    return JsonResponse(detail, status=502)

# ===================== OAuth (client_credentials) =====================
def _get_oauth_token() -> str:
    now = int(time.time())
    if _OAUTH_CACHE["access_token"] and _OAUTH_CACHE["exp"] > now + 60:
        return _OAUTH_CACHE["access_token"]

    client_id = (getattr(settings, "SERVICE_FUSION_CLIENT_ID", "") or "").strip()
    client_secret = (getattr(settings, "SERVICE_FUSION_CLIENT_SECRET", "") or "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("SERVICE_FUSION_CLIENT_ID / SERVICE_FUSION_CLIENT_SECRET manquants.")

    data = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
    r = requests.post(
        TOKEN_URL,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        data=data,
        timeout=_timeout(),
    )
    if r.status_code != 200:
        raise RuntimeError(f"OAuth token failed: {r.status_code} {r.text[:300]}")

    j = r.json()
    tok = j.get("access_token")
    if not tok:
        raise RuntimeError(f"OAuth response without access_token: {j}")

    try:
        ttl = int(j.get("expires_in", "3600"))
    except Exception:
        ttl = 3600
    _OAUTH_CACHE["access_token"] = tok
    _OAUTH_CACHE["exp"] = now + ttl
    return tok

def _headers_json() -> Dict[str, str]:
    tok = _get_oauth_token()
    return {"Authorization": f"Bearer {tok}", "Accept": "application/json", "Content-Type": "application/json"}

def _url(path: str) -> str:
    return f"{API_BASE}/{API_VERSION}{path if path.startswith('/') else '/' + path}"

def _get(path: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    r = requests.get(_url(path), headers=_headers_json(), params=params or {}, timeout=_timeout())
    r.raise_for_status()
    return r

def _post(path: str, json_body: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> requests.Response:
    r = requests.post(_url(path), headers=_headers_json(), json=json_body, params=params or {}, timeout=_timeout())
    r.raise_for_status()
    return r

def _patch(path: str, json_body: Dict[str, Any]) -> requests.Response:
    r = requests.patch(_url(path), headers=_headers_json(), json=json_body, timeout=_timeout())
    r.raise_for_status()
    return r

# ===================== API — Customers =====================
def api_customers_search(q: str) -> list[dict]:
    params = {
        "filters[name]": q,
        "expand": "contacts,contacts.phones,contacts.emails,locations",
        "per-page": 25,
        "fields": "id,customer_name,contacts,locations",
    }
    r = _get("/customers", params=params)
    data = r.json() if r.content else {}
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    return []

def api_customer_by_id(cid: int | str) -> dict:
    r = _get(f"/customers/{cid}", params={"expand": "contacts,contacts.phones,contacts.emails,locations"})
    return r.json() if r.content else {}

def api_job_by_id(jid: int | str) -> dict:
    r = _get(f"/jobs/{jid}", params={"expand": "notes,visits"})
    return r.json() if r.content else {}

# ---------- AJOUTS: création client ----------
def api_customer_create_minimal(customer_name: str) -> dict:
    """
    Crée un client minimal (beaucoup de tenants n’exigent que customer_name).
    Retourne l’objet JSON renvoyé par Service Fusion.
    """
    body = {"customer_name": _norm(customer_name)}
    r = _post("/customers", body)
    return r.json() if r.content else {}

def api_location_create_for_customer(customer_id: Any, loc: Dict[str, Any]) -> Optional[dict]:
    """
    Best-effort: crée une localisation primaire liée au client.
    Si l’API du tenant ne l’autorise pas, on ignore l’erreur pour ne pas bloquer.
    """
    body = {
        "customer_id": customer_id,
        "nickname": _norm(loc.get("name") or "Primary"),
        "street_1": _norm(loc.get("address") or loc.get("street_1")),
        "city": _norm(loc.get("city")),
        "state_prov": _norm(loc.get("state")),
        "postal_code": _norm(loc.get("zip")),
        "is_primary": True,
        "is_bill_to": True,
    }
    body = {k: v for k, v in body.items() if v not in (None, "", [])}
    if "customer_id" not in body:
        return None
    try:
        r = _post("/locations", body)
        return r.json() if r.content else {}
    except Exception:
        # On ne bloque pas si la création de location échoue.
        return None
# ---------- fin AJOUTS ----------

# ===================== Mapping Catégorie / Statut =====================
def _map_category(ui_value: str | None) -> Optional[str]:
    if not ui_value:
        return None
    ui_value = _norm(ui_value)
    mapped = CATEGORY_MAP.get(ui_value) or ui_value
    return mapped if mapped in ALLOWED_CATEGORIES else None

def _map_status(ui_value: str | None) -> str:
    if not ui_value:
        return STATUS_DEFAULT

    def norm_status(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip()).lower()

    wanted = norm_status(ui_value)
    for s in ALLOWED_STATUSES:
        if norm_status(s) == wanted:
            return s

    aliases = {
        "new": "Unscheduled",
        "unschedule": "Unscheduled",
        "dispatch": "Dispatched",
        "onsite": "On Site",
        "on the way": "On The Way",
        "started": "Started",
        "scheduled": "Scheduled",
        "paused": "Paused",
        "completed": "Completed",
        "cancelled": "Cancelled",
    }
    return aliases.get(wanted, STATUS_DEFAULT)

# ===================== API — Jobs (création robuste) =====================
def build_sf_job_payload(form_payload: Dict[str, Any]) -> Dict[str, Any]:
    customer_name = _norm(form_payload.get("customer_name"))
    location = form_payload.get("service_location") or {}
    contact = form_payload.get("contact") or {}
    category_ui = form_payload.get("category")
    priority = form_payload.get("priority") or "Normal"
    problem = form_payload.get("problem_details") or ""
    status_ui = form_payload.get("status")
    technician_name = form_payload.get("technician", "AnswringAgent AfterHours")

    desc_lines = [problem.strip()] if problem else []
    c_name = _norm(contact.get("name"))
    c_phone = _norm(contact.get("phone"))
    c_email = _norm(contact.get("email"))
    extra = []
    if c_name:  extra.append(f"Contact: {c_name}")
    if c_phone: extra.append(f"Phone: {c_phone}")
    if c_email: extra.append(f"Email: {c_email}")
    if extra: desc_lines.append(" | ".join(extra))
    description = "\n".join([ln for ln in desc_lines if ln]).strip() or "Work order created via integration."

    # Créer l'objet technicien basé sur le nom fourni
    technician_parts = technician_name.split(" ", 1)
    technician_obj = {
        "id": 980629768,  # ID réel du technicien "AnswringAgent AfterHours" dans Service Fusion
        "first_name": technician_parts[0] if technician_parts else "AnswringAgent",
        "last_name": technician_parts[1] if len(technician_parts) > 1 else "AfterHours"
    }

    payload: Dict[str, Any] = {
        "customer_name": customer_name,
        "location_name": _norm(location.get("name")),
        "street_1": _norm(location.get("address")),
        "city": _norm(location.get("city")),
        "state_prov": _norm(location.get("state")),
        "postal_code": _norm(location.get("zip")),
        "priority": priority,
        "description": description,
        "status": _map_status(status_ui),
        # Assignation du technicien spécifié
        "techs_assigned": [technician_obj]
    }
    mapped_cat = _map_category(category_ui)
    if mapped_cat:
        payload["category"] = mapped_cat
    else:
        # Service Fusion exige qu'une catégorie soit fournie
        payload["category"] = "Warranty"  # Catégorie par défaut

    return {k: v for k, v in payload.items() if v not in (None, "", "None")}

def api_job_create_strict(form_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_sf_job_payload(form_payload)
    r = _post("/jobs", payload, params={
        "fields": "id,number,status,customer_name,description,priority,created_at,location_name,category",
        "expand": "notes",
    })
    return r.json() if r.content else {}

def api_job_patch_description(job_id: Any, description: str) -> None:
    try:
        _patch(f"/jobs/{job_id}", {"description": description})
    except Exception:
        pass

def api_job_add_note(job_id: Any, text: str) -> None:
    try:
        _post(f"/jobs/{job_id}/notes", {"note": text, "visibility": "internal"})
    except Exception:
        pass

# ===================== LLM + Email (RESTORED) =====================
def _llm_headers() -> Dict[str, str]:
    return {"Content-Type": "application/json", "x-api-key": getattr(settings, "LLM_API_KEY", "")}

def call_llm(name: str, title: str, description: str) -> Dict[str, Any]:
    """
    Calls your external LLM summarizer. Returns {"links": {...}, "rag_url": "..."} (best-effort).
    If LLM_API_URL is not set, returns {} without raising.
    """
    url = getattr(settings, "LLM_API_URL", "")
    if not url:
        return {}
    r = requests.post(url, headers=_llm_headers(), json={
        "name": name or "Client",
        "title": title or "Note",
        "description": description or "",
    }, timeout=_timeout())
    r.raise_for_status()
    data = r.json() if r.content else {}
    links = data.get("links") or {}
    rag_url = links.get("docx") or links.get("json")
    return {"links": links, "rag_url": rag_url, "raw": data}

# ===================== Email helpers =====================
# The ONLY changes in this file are in this section below.

def _smtp_creds() -> Dict[str, Any]:
    """
    Normalize SMTP credentials from settings.
    Supports both Gmail and Mailjet configurations.
    """
    host = (getattr(settings, "EMAIL_HOST", "") or "").strip()
    port = int(getattr(settings, "EMAIL_PORT", 0) or 0)
    user = (getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    pwd = (getattr(settings, "EMAIL_HOST_PASSWORD", "") or "").strip()
    use_tls = bool(getattr(settings, "EMAIL_USE_TLS", False))
    use_ssl = bool(getattr(settings, "EMAIL_USE_SSL", False))
    timeout = int(getattr(settings, "EMAIL_TIMEOUT", 30) or 30)
    return {
        "host": host, "port": port, "user": user, "pwd": pwd,
        "use_tls": use_tls, "use_ssl": use_ssl, "timeout": timeout,
    }

def _conn_from_settings():
    """
    Primary SMTP connection using the project's email settings.
    We sanitize username/password and rely on Django's EmailBackend to STARTTLS when requested.
    """
    creds = _smtp_creds()
    return get_connection(
        backend=getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"),
        host=creds["host"] or None,
        port=creds["port"] or None,
        username=creds["user"] or None,
        password=creds["pwd"] or None,
        use_tls=creds["use_tls"],
        use_ssl=creds["use_ssl"],
        timeout=creds["timeout"],
    )

def _conn_gmail_ssl():
    """
    Gmail SSL:465 fallback. This uses the same sanitized username/password.
    """
    creds = _smtp_creds()
    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host="smtp.gmail.com",
        port=465,
        username=creds["user"] or None,
        password=creds["pwd"] or None,
        use_tls=False,
        use_ssl=True,
        timeout=creds["timeout"],
    )

def _resolve_from_addresses() -> tuple[str, dict]:
    """
    Resolve sender addresses for email sending.
    For Mailjet: Use the sender email from DEFAULT_FROM_EMAIL
    For Gmail: Use EMAIL_HOST_USER as envelope sender
    Returns (envelope_from_email, headers)
    """
    user_addr = (getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    display = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    host = (getattr(settings, "EMAIL_HOST", "") or "").strip().lower()

    # For Mailjet, use the sender email from DEFAULT_FROM_EMAIL
    if "mailjet" in host:
        # Extract email from DEFAULT_FROM_EMAIL (e.g., "AI_WORK_ORDER <operation@blue-collar.us>")
        import re
        email_match = re.search(r'<([^>]+)>', display)
        if email_match:
            envelope_from = email_match.group(1)
        else:
            envelope_from = display or "no-reply@localhost"
    else:
        # For Gmail, use EMAIL_HOST_USER as envelope sender
        envelope_from = user_addr or display or "no-reply@localhost"
    
    headers = {}

    # If a branded DEFAULT_FROM_EMAIL exists, pass it via the 'From' header
    if display and envelope_from:
        headers["From"] = display

    return envelope_from, headers

def _send_html_email(subject: str, html: str, to_email: str) -> bool:
    """
    Robust HTML sender with strict Gmail/Workspace compatibility.
    Steps:
      1) Validate recipient; build a primary SMTP connection (STARTTLS 587 if configured).
      2) Force envelope sender to SMTP username; keep display name in 'From' header.
      3) On 535 or any SMTP error, retry with SSL:465 fallback.
      4) If everything fails, print to console backend so no data is lost.
    """
    recipient = (to_email or getattr(settings, "WORKORDER_RECIPIENT", "")).strip()
    print(f"🔍 DEBUG EMAIL: to_email='{to_email}', WORKORDER_RECIPIENT='{getattr(settings, 'WORKORDER_RECIPIENT', '')}', final_recipient='{recipient}'")
    if not recipient:
        print("⚠️ No recipient provided; skip email.")
        return False

    # Resolve envelope sender + branded header.
    from_email, from_headers = _resolve_from_addresses()
    print(f"🔍 DEBUG EMAIL: from_email='{from_email}', from_headers={from_headers}")

    # 1) Primary connection (from settings).
    try:
        with _conn_from_settings() as conn:
            msg = EmailMessage(
                subject=subject,
                body=html,
                from_email=from_email,   # envelope sender MUST match SMTP auth user for Gmail
                to=[recipient],
                connection=conn,
                headers=from_headers     # keep 'Bluecollar <...>' display if configured
            )
            msg.content_subtype = "html"
            msg.send(fail_silently=False)
        print("✅ HTML Email sent (primary SMTP settings).")
        return True
    except Exception as e1:
        # Provide a targeted hint when Gmail refuses credentials.
        msg = str(e1)
        if "535" in msg and "Username and Password not accepted" in msg:
            print("❌ SMTP 535 (primary): Gmail/Workspace rejected credentials. "
                  "Ensure EMAIL_HOST_USER is the mailbox and EMAIL_HOST_PASSWORD is an App Password.")
        else:
            print(f"❌ SMTP send error (primary): {e1}")

    # 2) Gmail SSL:465 fallback — only if host is gmail or unspecified (keeps prior behavior).
    try:
        host = (getattr(settings, "EMAIL_HOST", "") or "").lower().strip()
        if "gmail.com" in host or host == "":
            with _conn_gmail_ssl() as conn:
                msg = EmailMessage(
                    subject=subject,
                    body=html,
                    from_email=from_email,
                    to=[recipient],
                    connection=conn,
                    headers=from_headers
                )
                msg.content_subtype = "html"
                msg.send(fail_silently=False)
            print("✅ HTML Email sent (fallback Gmail SSL:465).")
            return True
    except Exception as e2:
        msg = str(e2)
        if "535" in msg and "Username and Password not accepted" in msg:
            print("❌ SMTP 535 (gmail ssl fallback): Gmail/Workspace rejected credentials. "
                  "Verify that the account uses an App Password and the domain is on Google Workspace.")
        else:
            print(f"❌ SMTP send error (gmail ssl fallback): {e2}")

    # 3) Console fallback (no external SMTP; guarantees traceability).
    try:
        from django.core.mail import get_connection as gc
        with gc("django.core.mail.backends.console.EmailBackend") as conn:
            msg = EmailMessage(
                subject=subject,
                body=html,
                from_email=from_email,
                to=[recipient],
                connection=conn,
                headers=from_headers
            )
            msg.content_subtype = "html"
            msg.send(fail_silently=True)
        print("ℹ️ HTML Email printed to console backend as fallback.")
    except Exception as e3:
        print(f"⚠️ Console email fallback failed: {e3}")
    return False

def _render_email(template_ctx: Dict[str, Any]) -> str:
    """
    Renders the email HTML using templates/send_mail.html
    """
    return render_to_string("send_mail.html", template_ctx or {})

# ---- Legacy text email kept intact (not used by new HTML flow but preserved) ----
def email_workorder(subject: str, lines: list[str], to_email: Optional[str] = None) -> bool:
    recipient = (to_email or getattr(settings, "WORKORDER_RECIPIENT", "")).strip()
    if not recipient:
        print("⚠️ No recipient provided; skip email.")
        return False

    # Force envelope sender to SMTP user for Gmail compliance.
    from_email, from_headers = _resolve_from_addresses()

    body = "\n".join(lines).strip()
    try:
        with _conn_from_settings() as conn:
            EmailMessage(
                subject=subject,
                body=body,
                from_email=from_email,
                to=[recipient],
                connection=conn,
                headers=from_headers
            ).send(fail_silently=False)
        return True
    except Exception:
        try:
            with _conn_gmail_ssl() as conn:
                EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient],
                    connection=conn,
                    headers=from_headers
                ).send(fail_silently=False)
            return True
        except Exception:
            try:
                from django.core.mail import get_connection as gc
                with gc("django.core.mail.backends.console.EmailBackend") as conn:
                    EmailMessage(
                        subject=subject,
                        body=body,
                        from_email=from_email,
                        to=[recipient],
                        connection=conn,
                        headers=from_headers
                    ).send(fail_silently=True)
            except Exception:
                pass
    return False
# -----------------------------------------------------------------------------

# ===================== API JSON (front) =====================
def sf_search_customers(request: HttpRequest):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse([], safe=False)
    try:
        items = api_customers_search(q)
        for it in items:
            if "name" not in it and "customer_name" in it:
                it["name"] = it["customer_name"]
        return JsonResponse(items, safe=False)
    except requests.HTTPError as he:
        return _json_error(he, "customers", he.response)
    except Exception as e:
        return _json_error(e, "customers")

def sf_get_customer(request: HttpRequest, cid: str):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = api_customer_by_id(cid)
        return JsonResponse(data, safe=False)
    except requests.HTTPError as he:
        return _json_error(he, "customers", he.response)
    except Exception as e:
        return _json_error(e, "customers")

def sf_get_job(request: HttpRequest, jid: str):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = api_job_by_id(jid)
        return JsonResponse(data, safe=False)
    except requests.HTTPError as he:
        return _json_error(he, "jobs", he.response)
    except Exception as e:
        return _json_error(e, "jobs")

# ---------- AJOUT: endpoint POST /sf/customers ----------
@csrf_exempt
def sf_create_customer(request: HttpRequest):
    """
    Crée un client Service Fusion (minimal), puis essaie d’ajouter une localisation primaire.
    Envoie un e-mail HTML de notification avec les informations du client créé.
    JSON attendu:
    { "customer_name": "...", "service_location": {...}, "contact": {...}, "email": {"to": "..."} }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        cname = _norm(payload.get("customer_name"))
        if not cname:
            return JsonResponse({"error": "customer_name is required"}, status=400)

        # 1) Create minimal customer
        cust = api_customer_create_minimal(cname)
        cust_id = _safe_get(cust, "id") or _safe_get(cust, "customer_id")
        if not cust_id:
            return JsonResponse({"error": "Create customer failed", "raw": cust}, status=502)

        # 2) Best-effort location
        loc = payload.get("service_location") or {}
        if loc:
            api_location_create_for_customer(cust_id, loc)

        # 3) Fetch full (best-effort)
        try:
            full = api_customer_by_id(cust_id)
        except Exception:
            full = {"id": cust_id, "customer_name": cname}

        # 4) Send HTML notification
        to_email = _safe_get(payload, "email", "to")
        ctx = {
            "type": "customer_created",
            "brand": {"name": "BlueCollar AI"},
            "customer": {
                "id": full.get("id"),
                "name": full.get("customer_name") or cname,
                "contact": _safe_get(payload, "contact") or {},
            },
            "location": {
                "name": loc.get("name") or "",
                "address": (loc.get("address") or loc.get("street_1") or ""),
                "city": loc.get("city") or "",
                "state": loc.get("state") or "",
                "zip": loc.get("zip") or "",
            },
            "links": {},
        }
        html = _render_email(ctx)
        _send_html_email(subject=f"[Customer Created] {cname}", html=html, to_email=to_email or getattr(settings, "WORKORDER_RECIPIENT", ""))

        return JsonResponse(full, safe=False, status=200)

    except requests.HTTPError as he:
        return _json_error(he, "customers", he.response)
    except Exception as e:
        return _json_error(e, "customers")
# ---------- fin AJOUT ----------

@csrf_exempt
def sf_create_job(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        # 1) Créer le job
        job_resp = api_job_create_strict(payload)
        job_id = _safe_get(job_resp, "id") or _safe_get(job_resp, "job_id") or _safe_get(job_resp, "data", "id")
        job_number = _safe_get(job_resp, "number") or _safe_get(job_resp, "data", "number")
        job_api_url = f"{API_BASE}/{API_VERSION}/jobs/{job_id}" if job_id else None

        # 2) LLM & enrichissements
        customer_name = _norm(payload.get("customer_name"))
        category = payload.get("category") or payload.get("category_ui") or ""
        priority = payload.get("priority") or "Normal"
        problem = payload.get("problem_details") or ""
        llm = call_llm(customer_name or "Client", f"{category}/{priority}", problem)  # <-- RESTORED
        links, rag = llm.get("links", {}), llm.get("rag_url")

        if job_id and (rag or links):
            extras = []
            if rag: extras.append(f"RAG: {rag}")
            if links.get("docx"): extras.append(f"Doc: {links['docx']}")
            if extras:
                try:
                    cur_desc = _safe_get(job_resp, "description") or problem or ""
                    new_desc = (cur_desc + "\n\n" + "\n".join(extras)).strip()
                    api_job_patch_description(job_id, new_desc)
                except Exception:
                    pass
                note = ["Auto-generated summary links:"]
                if rag: note.append(f"- RAG: {rag}")
                if links.get("docx"): note.append(f"- DOCX: {links['docx']}")
                api_job_add_note(job_id, "\n".join(note))

        # 3) Email HTML
        to_email = _safe_get(payload, "email", "to")
        ctx = {
            "type": "job_created",
            "brand": {"name": "BlueCollar AI"},
            "job": {
                "id": job_id,
                "number": job_number,
                "status": _safe_get(job_resp, "status"),
                "priority": _safe_get(job_resp, "priority") or payload.get("priority"),
                "category": _safe_get(job_resp, "category") or payload.get("category"),
                "created_at": _safe_get(job_resp, "created_at"),
                "api_url": job_api_url,
                "description": problem or "(empty)",
            },
            "customer": {
                "name": _norm(payload.get("customer_name")),
                "contact": _safe_get(payload, "contact") or {},
            },
            "location": {
                "name": _safe_get(payload, "service_location", "name") or "",
                "address": _safe_get(payload, "service_location", "address") or "",
            },
            "links": {
                "docx": links.get("docx"),
                "json": links.get("json"),
                "rag": rag,
            },
        }
        html = _render_email(ctx)
        email_ok = _send_html_email(
            subject=f"[Work Order] {ctx['customer']['name']} — {category}/{priority}",
            html=html,
            to_email=to_email or getattr(settings, "WORKORDER_RECIPIENT", "")
        )

        return JsonResponse({
            "ok": True,
            "job_id": job_id,
            "job_number": job_number,
            "job_api_url": job_api_url,
            "email_status": "sent" if email_ok else "unknown",
            "links": links, "rag_url": rag,
            "service_fusion": job_resp,
        }, status=200)

    except requests.HTTPError as he:
        return _json_error(he, "jobs", he.response)
    except Exception as e:
        return _json_error(e, "jobs")

# ===================== Page HTML simple (form) =====================
def fsm_wizard(request: HttpRequest):
    ctx = {
        "today": time.strftime("%Y-%m-%d"),
        "categories": ["Refrigeration", "Plumbing", "Electrical", "HVAC", "General Maintenance"],
        "statuses": ALLOWED_STATUSES,
    }
    return render(request, "fsm_platform_server.html", ctx)

def platform_server(request: HttpRequest):
    return render(request, "fsm_platform_server.html")

def bluecollar_main_platform(request: HttpRequest):
    return render(request, "bluecollar_main_platform.html")

# ===================== Debug =====================
def sf_oauth_test(request: HttpRequest):
    try:
        tok = _get_oauth_token()
        ping = requests.get(f"{API_BASE}/{API_VERSION}/customers",
                            headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"},
                            timeout=_timeout())
        return JsonResponse({"ok": True, "token_prefix": tok[:12] + "...", "ping_status": ping.status_code})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)