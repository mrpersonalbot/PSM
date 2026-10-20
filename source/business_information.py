"""Central owner-approved PSM identity, address, operating hours, and Maps destination.

Generated page templates are legacy inputs; normalize their business information
here so headers, footers, landing pages, and structured data stay consistent.
"""

import json
import re
import unicodedata
from copy import deepcopy
from html import unescape
from urllib.parse import parse_qs, unquote, urlsplit

BUSINESS_INFO = {
    "legal_name": "CV Pratama Sukses Mandiri",
    "street_address": "Jl. Ujung Belakang Olo No. 14e",
    "maps_url": "https://share.google/WOR9AeR91epH32LOo",
    "operating_hours": {
        "weekdays": {
            "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "opens": "09:00",
            "closes": "18:00",
            "display": "09.00–18.00",
        },
        "saturday": {
            "day": "Saturday",
            "opens": "09:00",
            "closes": "17:00",
            "display": "09.00–17.00",
        },
        "sunday": {"day": "Sunday", "closed": True, "display": "Tutup"},
    },
}

_STORE_TYPES = {"hardwarestore", "electricalsupplystore", "localbusiness", "store"}
_ADDRESS_PATTERN = re.compile(
    r"(?P<prefix>Jl\.\s*Ujung Belakang Olo\s+)No\.\s*14(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_SATURDAY_TEXT_PATTERN = re.compile(
    r"(?P<label>Sabtu|Sab)(?P<separator>:</b>\s*|</span>\s*<b>|\s+)"
    r"08[.:]00\s*[–-]\s*17[.:]00",
    re.IGNORECASE,
)
_MAPS_HREF_PATTERN = re.compile(
    r"(?P<prefix>\bhref\s*=\s*)(?P<quote>[\"'])"
    r"(?P<url>[^\"']*)(?P=quote)",
    re.IGNORECASE,
)
_JSONLD_SCRIPT_PATTERN = re.compile(
    r'(<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>)'
    r"(.*?)"
    r"(</script\s*>)",
    re.IGNORECASE | re.DOTALL,
)


def _is_store_entity(value):
    entity_types = value.get("@type", [])
    if isinstance(entity_types, str):
        entity_types = [entity_types]
    return any(str(entity_type).rsplit("/", 1)[-1].casefold() in _STORE_TYPES for entity_type in entity_types)


def _is_organization_entity(value):
    entity_types = value.get("@type", [])
    if isinstance(entity_types, str):
        entity_types = [entity_types]
    return any(str(entity_type).rsplit("/", 1)[-1].casefold() == "organization" for entity_type in entity_types)


def _day_name(value):
    return str(value).rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1].casefold()


def _day_values_field(original, values):
    if isinstance(original, list):
        return values
    return values[0] if values else original


def _is_psm_legal_entity_name(value):
    normalized = re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())
    return normalized in {"ptpratamasuksesmandiri", "cvpratamasuksesmandiri"}


def has_legacy_psm_legal_entity_reference(value):
    """Detect the incorrect PSM legal name in plain or encoded public text."""
    candidate = str(value or "")
    for _ in range(5):
        normalized = unicodedata.normalize("NFKC", candidate).casefold()
        compact = re.sub(r"[^a-z0-9]+", "", normalized)
        if "ptpratamasuksesmandiri" in compact:
            return True
        decoded = re.sub(
            re.escape(chr(92)) + r"u([0-9a-fA-F]{4})",
            lambda match: chr(int(match.group(1), 16)),
            candidate,
        )
        decoded = re.sub(
            re.escape(chr(92)) + r"x([0-9a-fA-F]{2})",
            lambda match: chr(int(match.group(1), 16)),
            decoded,
        )
        decoded = unescape(unquote(decoded))
        if decoded == candidate:
            break
        candidate = decoded
    normalized = unicodedata.normalize("NFKC", candidate).casefold()
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    return "ptpratamasuksesmandiri" in compact


def _opening_hours_specification(entity):
    raw_specs = entity.get("openingHoursSpecification")
    if raw_specs is None:
        raw_specs = []
    elif isinstance(raw_specs, dict):
        raw_specs = [raw_specs]
    elif not isinstance(raw_specs, list):
        raise ValueError("openingHoursSpecification must be an object or array")

    weekday_hours = BUSINESS_INFO["operating_hours"]["weekdays"]
    saturday_hours = BUSINESS_INFO["operating_hours"]["saturday"]
    weekday_names = {day.casefold() for day in weekday_hours["days"]}
    covered_weekdays = set()
    covered_saturday = False
    normalized_specs = []

    for spec in raw_specs:
        if not isinstance(spec, dict) or "dayOfWeek" not in spec:
            normalized_specs.append(spec)
            continue

        original_days = spec["dayOfWeek"]
        day_values = original_days if isinstance(original_days, list) else [original_days]
        weekdays = [day for day in day_values if _day_name(day) in weekday_names]
        saturdays = [day for day in day_values if _day_name(day) == "saturday"]
        other_days = [
            day for day in day_values
            if _day_name(day) not in weekday_names | {"saturday", "sunday"}
        ]

        if weekdays:
            weekday_spec = deepcopy(spec)
            weekday_spec["dayOfWeek"] = _day_values_field(original_days, weekdays)
            weekday_spec["opens"] = weekday_hours["opens"]
            weekday_spec["closes"] = weekday_hours["closes"]
            normalized_specs.append(weekday_spec)
            covered_weekdays.update(_day_name(day) for day in weekdays)

        if saturdays:
            saturday_spec = deepcopy(spec)
            saturday_spec["dayOfWeek"] = _day_values_field(original_days, saturdays)
            saturday_spec["opens"] = saturday_hours["opens"]
            saturday_spec["closes"] = saturday_hours["closes"]
            normalized_specs.append(saturday_spec)
            covered_saturday = True

        if other_days:
            other_spec = deepcopy(spec)
            other_spec["dayOfWeek"] = _day_values_field(original_days, other_days)
            normalized_specs.append(other_spec)
        # Sunday is intentionally omitted: the approved schedule is closed.

    missing_weekdays = [day for day in weekday_hours["days"] if day.casefold() not in covered_weekdays]
    if missing_weekdays:
        normalized_specs.append(
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": missing_weekdays,
                "opens": weekday_hours["opens"],
                "closes": weekday_hours["closes"],
            }
        )
    if not covered_saturday:
        normalized_specs.append(
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": saturday_hours["day"],
                "opens": saturday_hours["opens"],
                "closes": saturday_hours["closes"],
            }
        )

    entity["openingHoursSpecification"] = normalized_specs


def _update_store_entity(entity):
    address = entity.get("address")
    if not isinstance(address, dict):
        address = {"@type": "PostalAddress"}
        entity["address"] = address
    address["streetAddress"] = BUSINESS_INFO["street_address"]
    entity["legalName"] = BUSINESS_INFO["legal_name"]
    entity["hasMap"] = BUSINESS_INFO["maps_url"]
    _opening_hours_specification(entity)


def _walk_jsonld(value):
    if isinstance(value, list):
        for item in value:
            _walk_jsonld(item)
    elif isinstance(value, dict):
        if "legalName" in value and _is_psm_legal_entity_name(value["legalName"]):
            value["legalName"] = BUSINESS_INFO["legal_name"]
        if (
            (_is_store_entity(value) or _is_organization_entity(value))
            and _is_psm_legal_entity_name(value.get("name"))
        ):
            value["name"] = BUSINESS_INFO["legal_name"]
        seller = value.get("seller")
        if isinstance(seller, str) and _is_psm_legal_entity_name(seller):
            value["seller"] = BUSINESS_INFO["legal_name"]
        elif isinstance(seller, dict) and _is_psm_legal_entity_name(seller.get("name")):
            seller["name"] = BUSINESS_INFO["legal_name"]
        if _is_store_entity(value):
            _update_store_entity(value)
        for child in value.values():
            _walk_jsonld(child)


def _is_psm_store_maps_url(value):
    url = unescape(value).strip()
    parts = urlsplit(url)
    host = parts.netloc.casefold()
    if host == "share.google":
        return True
    if host not in {"google.com", "www.google.com"} or not parts.path.startswith("/maps/search"):
        return False
    query = " ".join(parse_qs(parts.query).get("query", [])).casefold()
    return "pratama" in query or "ujung belakang olo" in query


def apply_business_information(page_html):
    """Apply the centralized owner-approved business data to generated HTML."""
    page_html = _ADDRESS_PATTERN.sub(
        lambda match: match.group("prefix") + "No. 14e",
        page_html,
    )
    page_html = _SATURDAY_TEXT_PATTERN.sub(
        lambda match: match.group("label") + match.group("separator") + "09.00–17.00",
        page_html,
    )

    def replace_map_href(match):
        if not _is_psm_store_maps_url(match.group("url")):
            return match.group(0)
        return match.group("prefix") + match.group("quote") + BUSINESS_INFO["maps_url"] + match.group("quote")

    page_html = _MAPS_HREF_PATTERN.sub(replace_map_href, page_html)

    def update_jsonld(match):
        raw_json = match.group(2)
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return match.group(0)
        before = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        _walk_jsonld(data)
        after = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if before == after:
            return match.group(0)
        return match.group(1) + after + match.group(3)

    return _JSONLD_SCRIPT_PATTERN.sub(update_jsonld, page_html)
