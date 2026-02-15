"""Address normalization and parsing utilities using usaddress."""

import logging
import re

import usaddress

log = logging.getLogger(__name__)

# Standard abbreviation mappings
STREET_SUFFIX_MAP = {
    "STREET": "ST", "AVENUE": "AVE", "BOULEVARD": "BLVD", "DRIVE": "DR",
    "ROAD": "RD", "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR",
    "PLACE": "PL", "TERRACE": "TER", "TRAIL": "TRL", "WAY": "WAY",
    "HIGHWAY": "HWY", "PARKWAY": "PKWY", "EXPRESSWAY": "EXPY",
    "FREEWAY": "FWY", "PIKE": "PIKE", "TURNPIKE": "TPKE",
}

UNIT_TYPE_MAP = {
    "SUITE": "STE", "APARTMENT": "APT", "BUILDING": "BLDG",
    "UNIT": "UNIT", "ROOM": "RM", "FLOOR": "FL", "DEPARTMENT": "DEPT",
    "NUMBER": "#", "SPACE": "SPC", "LOT": "LOT",
}

DIRECTION_MAP = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}

STATE_NAMES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC", "PUERTO RICO": "PR", "GUAM": "GU",
    "VIRGIN ISLANDS": "VI", "AMERICAN SAMOA": "AS",
}


def clean_text(text: str | None) -> str | None:
    """Uppercase, strip punctuation and extra whitespace."""
    if not text:
        return None
    text = text.upper().strip()
    text = re.sub(r"[.,#]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text or None


def normalize_state(state: str | None) -> str | None:
    """Convert state name or code to 2-letter abbreviation."""
    if not state:
        return None
    state = state.upper().strip()
    if len(state) == 2:
        return state
    return STATE_NAMES.get(state, state[:2] if len(state) > 2 else state)


def normalize_zip(zip_code: str | None) -> tuple[str | None, str | None]:
    """Extract ZIP5 and ZIP4 from various formats."""
    if not zip_code:
        return None, None
    zip_code = re.sub(r"[^0-9]", "", str(zip_code))
    if len(zip_code) >= 9:
        return zip_code[:5], zip_code[5:9]
    if len(zip_code) >= 5:
        return zip_code[:5], None
    return None, None


def abbreviate_suffix(suffix: str) -> str:
    """Standardize street suffix abbreviations."""
    suffix = suffix.upper().strip().rstrip(".")
    return STREET_SUFFIX_MAP.get(suffix, suffix)


def abbreviate_unit_type(unit_type: str) -> str:
    """Standardize unit type abbreviations."""
    unit_type = unit_type.upper().strip().rstrip(".")
    return UNIT_TYPE_MAP.get(unit_type, unit_type)


def abbreviate_direction(direction: str) -> str:
    """Standardize directional abbreviations."""
    direction = direction.upper().strip().rstrip(".")
    return DIRECTION_MAP.get(direction, direction)


def parse_street_address(street_line: str | None) -> dict:
    """
    Parse a street address into components using usaddress.

    Returns dict with keys: street_number, street_name, street_suffix,
    unit_type, unit_number.
    """
    result = {
        "street_number": None,
        "street_name": None,
        "street_suffix": None,
        "unit_type": None,
        "unit_number": None,
    }

    if not street_line:
        return result

    cleaned = clean_text(street_line)
    if not cleaned:
        return result

    try:
        tagged, addr_type = usaddress.tag(cleaned)
    except usaddress.RepeatedLabelError:
        log.debug("usaddress repeated label for: %s", cleaned)
        return result

    result["street_number"] = tagged.get("AddressNumber")

    # Build street name from components
    name_parts = []
    for key in ["StreetNamePreDirectional", "StreetNamePreType",
                "StreetNamePreModifier", "StreetName"]:
        val = tagged.get(key)
        if val:
            if key == "StreetNamePreDirectional":
                val = abbreviate_direction(val)
            name_parts.append(val)
    result["street_name"] = " ".join(name_parts) if name_parts else None

    suffix = tagged.get("StreetNamePostType")
    if suffix:
        result["street_suffix"] = abbreviate_suffix(suffix)

    unit_type = tagged.get("OccupancyType")
    if unit_type:
        result["unit_type"] = abbreviate_unit_type(unit_type)

    result["unit_number"] = tagged.get("OccupancyIdentifier")

    return result


def normalize_address(
    street_line_1: str | None,
    street_line_2: str | None,
    city: str | None,
    state: str | None,
    zip_code: str | None,
    phone: str | None = None,
    fax: str | None = None,
) -> dict:
    """
    Normalize a full address record.

    Returns a dict with all cleaned/parsed fields ready for DB insertion.
    """
    street_line_1 = clean_text(street_line_1)
    street_line_2 = clean_text(street_line_2)
    city = clean_text(city)
    state_code = normalize_state(state)
    zip5, zip4 = normalize_zip(zip_code)

    # Parse street components from line 1
    parsed = parse_street_address(street_line_1)

    # If line 2 looks like a unit, parse it
    if street_line_2 and not parsed["unit_type"]:
        line2_parsed = parse_street_address(street_line_2)
        if line2_parsed["unit_type"]:
            parsed["unit_type"] = line2_parsed["unit_type"]
            parsed["unit_number"] = line2_parsed["unit_number"]

    return {
        "street_line_1": street_line_1,
        "street_line_2": street_line_2,
        "city": city,
        "state_code": state_code,
        "zip5": zip5,
        "zip4": zip4,
        "country_code": "US",
        "phone": clean_text(phone),
        "fax": clean_text(fax),
        "street_number": parsed["street_number"],
        "street_name": parsed["street_name"],
        "street_suffix": parsed["street_suffix"],
        "unit_type": parsed["unit_type"],
        "unit_number": parsed["unit_number"],
    }
