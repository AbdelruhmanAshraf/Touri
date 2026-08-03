"""
Touri in-memory catalog.

Loads every CSV/XLSX in ``backend/data/egypt_csv`` once at startup, normalises
each row into a single ``CatalogItem`` shape, and exposes ergonomic query
helpers for the REST catalog routes (``/api/catalog/*``).

This module is intentionally pure-Python + pandas. The data is small enough
(~3.7k rows total) to keep in process memory, so we trade a few MB of RAM
for sub-millisecond lookups and zero database dependency.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

# ── Type aliases ──────────────────────────────────────────────────────────────
CatalogType = str  # "attraction" | "hotel" | "restaurant" | "transport" | "event" | "medical"
_EXCLUDED_TYPES: frozenset[str] = frozenset({"flight"})  # Touri is domestic-only; flights are not surfaced


@dataclass
class CatalogItem:
    """Single normalised entity from any of the source CSVs."""

    id: str
    type: CatalogType
    name: str
    city: str = ""
    subtype: str = ""
    rating: Optional[float] = None
    price_egp: Optional[float] = None
    price_usd: Optional[float] = None
    currency: str = ""
    image_urls: List[str] = field(default_factory=list)
    description: str = ""
    location_url: str = ""
    best_season: str = ""
    best_hours: str = ""
    entry_fee: str = ""
    distance_from_cairo_km: Optional[float] = None
    amenities: List[str] = field(default_factory=list)
    cuisine: str = ""
    dishes: List[str] = field(default_factory=list)
    dietary: List[str] = field(default_factory=list)
    reviews_summary: str = ""
    event_date: str = ""
    event_duration: str = ""
    audience: str = ""
    organizer: str = ""
    transport_from: str = ""
    transport_to: str = ""
    transport_mode: str = ""
    transport_duration_h: Optional[float] = None
    transport_frequency: str = ""
    airline: str = ""
    flight_duration_min: Optional[int] = None
    stops: str = ""
    weekly_flights: Optional[int] = None
    departure_date: str = ""
    booking_link: str = ""
    services: List[str] = field(default_factory=list)
    price_category: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "city": self.city,
            "subtype": self.subtype,
            "rating": self.rating,
            "price_egp": self.price_egp,
            "price_usd": self.price_usd,
            "currency": self.currency,
            "image_urls": self.image_urls,
            "description": self.description,
            "location_url": self.location_url,
            "best_season": self.best_season,
            "best_hours": self.best_hours,
            "entry_fee": self.entry_fee,
            "distance_from_cairo_km": self.distance_from_cairo_km,
            "amenities": self.amenities,
            "cuisine": self.cuisine,
            "dishes": self.dishes,
            "dietary": self.dietary,
            "reviews_summary": self.reviews_summary,
            "event_date": self.event_date,
            "event_duration": self.event_duration,
            "audience": self.audience,
            "organizer": self.organizer,
            "transport_from": self.transport_from,
            "transport_to": self.transport_to,
            "transport_mode": self.transport_mode,
            "transport_duration_h": self.transport_duration_h,
            "transport_frequency": self.transport_frequency,
            "airline": self.airline,
            "flight_duration_min": self.flight_duration_min,
            "stops": self.stops,
            "weekly_flights": self.weekly_flights,
            "departure_date": self.departure_date,
            "booking_link": self.booking_link,
            "services": self.services,
            "price_category": self.price_category,
        }

    def to_card(self) -> Dict[str, Any]:
        """Compact card payload for grids / carousels."""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "city": self.city,
            "subtype": self.subtype,
            "rating": self.rating,
            "price_egp": self.price_egp,
            "price_usd": self.price_usd,
            "currency": self.currency,
            "image": self.image_urls[0] if self.image_urls else "",
            "best_season": self.best_season,
            "best_hours": self.best_hours,
            "entry_fee": self.entry_fee,
            "event_date": self.event_date,
            "transport_from": self.transport_from,
            "transport_to": self.transport_to,
            "transport_mode": self.transport_mode,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────
def _clean(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() in ("nan", "none", "null") else s


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", _clean(value).lower())
    return value.strip("_") or "unknown"


def _to_float(value: Any) -> Optional[float]:
    s = _clean(value)
    if not s:
        return None
    # strip currency / units
    s = re.sub(r"[^0-9.\-]+", "", s)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(value: Any) -> Optional[int]:
    f = _to_float(value)
    return int(f) if f is not None else None


def _split_list(value: Any, sep: str = ",") -> List[str]:
    s = _clean(value)
    if not s:
        return []
    if ";" in s and sep not in s:
        sep = ";"
    parts = [p.strip() for p in s.split(sep) if p.strip()]
    return parts


def _drive_url_to_lh3(url: str) -> str:
    """Convert ``drive.google.com/uc?export=download&id=X`` → stable lh3 URL.

    The lh3.googleusercontent.com/d/{id}=w1000 form serves the image
    directly with no redirect/cookie shenanigans, which React Native's
    <Image> needs.
    """
    if not url:
        return ""
    m = re.search(r"[?&]id=([^&]+)", url)
    if m:
        return f"https://lh3.googleusercontent.com/d/{m.group(1)}=w1200"
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return f"https://lh3.googleusercontent.com/d/{m.group(1)}=w1200"
    return url


def _parse_image_urls(raw: Any) -> List[str]:
    s = _clean(raw)
    if not s:
        return []
    urls = [u.strip() for u in re.split(r"[;\n]+", s) if u.strip().startswith("http")]
    out: List[str] = []
    seen: set[str] = set()
    for u in urls[:10]:  # cap to 10 per item
        converted = _drive_url_to_lh3(u)
        if converted and converted not in seen:
            seen.add(converted)
            out.append(converted)
    return out


# ── Per-domain row → CatalogItem ──────────────────────────────────────────────
def _row_attraction(row: pd.Series, idx: int) -> CatalogItem:
    name = _clean(row.get("Attraction"))
    city = _clean(row.get("City"))
    return CatalogItem(
        id=f"attraction_{_slug(name)}_{_slug(city)}_{idx}",
        type="attraction",
        name=name or "Unknown attraction",
        city=city,
        subtype=_clean(row.get("Type")),
        rating=_to_float(row.get("Rating")),
        image_urls=_parse_image_urls(row.get("image_urls")),
        description=_clean(row.get("Description")),
        location_url=_clean(row.get("Location")),
        best_season=_clean(row.get("Best time to visit")),
        best_hours=_clean(row.get("Best hour to visit")),
        entry_fee=_clean(row.get("Entry fee")),
        distance_from_cairo_km=_to_float(row.get("Distance from Cairo (km)")),
        currency="EGP",
    )


def _row_hotel(row: pd.Series, idx: int) -> CatalogItem:
    name = _clean(row.get("Hotel Name"))
    city = _clean(row.get("City"))
    price = _to_float(row.get("Price (EGP)"))
    return CatalogItem(
        id=f"hotel_{_slug(name)}_{_slug(city)}_{idx}",
        type="hotel",
        name=name or "Unknown hotel",
        city=city,
        subtype="lodging",
        rating=_to_float(row.get("Rating")),
        price_egp=price,
        currency="EGP",
        amenities=_split_list(row.get("Amenities")),
    )


def _row_restaurant(row: pd.Series, idx: int) -> CatalogItem:
    name = _clean(row.get("Name"))
    city = _clean(row.get("City"))
    return CatalogItem(
        id=f"restaurant_{_slug(name)}_{_slug(city)}_{idx}",
        type="restaurant",
        name=name or "Unknown restaurant",
        city=city,
        subtype=_clean(row.get("Cuisine Type")),
        rating=_to_float(row.get("User Rating")),
        cuisine=_clean(row.get("Cuisine Type")),
        dishes=_split_list(row.get("Specialty Dishes")),
        dietary=_split_list(row.get("Dietary Options")),
        reviews_summary=_clean(row.get("Reviews")),
        location_url=_clean(row.get("Google Maps Link")),
        entry_fee=_clean(row.get("Price Range")),  # "Price Range" reused as the cost band
        currency="EGP",
    )


def _row_transport(row: pd.Series, idx: int) -> CatalogItem:
    frm = _clean(row.get("From_Province"))
    to = _clean(row.get("To_Province"))
    mode = _clean(row.get("Transport_Type"))
    return CatalogItem(
        id=f"transport_{_slug(frm)}_{_slug(to)}_{_slug(mode)}_{idx}",
        type="transport",
        name=f"{mode}: {frm} → {to}" if mode else f"{frm} → {to}",
        city=to,
        subtype=mode,
        price_egp=_to_float(row.get("Avg_Price_EGP")),
        currency="EGP",
        transport_from=frm,
        transport_to=to,
        transport_mode=mode,
        transport_duration_h=_to_float(row.get("Avg_Duration_Hours")),
        transport_frequency=_clean(row.get("Frequency")),
        organizer=_clean(row.get("Company_Name")),
        description=_clean(row.get("Notes")),
        distance_from_cairo_km=_to_float(row.get("Distance_KM")),
    )


def _row_flight(row: pd.Series, idx: int) -> CatalogItem:
    frm = _clean(row.get("From"))
    to = _clean(row.get("To"))
    airline = _clean(row.get("Airline"))
    return CatalogItem(
        id=f"flight_{_slug(frm)}_{_slug(to)}_{_slug(airline)}_{idx}",
        type="flight",
        name=f"{airline}: {frm} → {to}" if airline else f"{frm} → {to}",
        city=to,
        subtype=_clean(row.get("Class")) or "flight",
        price_usd=_to_float(row.get("Price (USD)")),
        currency="USD",
        airline=airline,
        flight_duration_min=_to_int(row.get("Flight Duration (Minutes)")),
        weekly_flights=_to_int(row.get("Weekly Flights")),
        stops=_clean(row.get("Stops")),
        departure_date=_clean(row.get("Departure Date")),
        booking_link=_clean(row.get("Airline Link")),
        transport_from=frm,
        transport_to=to,
    )


def _row_event(row: pd.Series, idx: int) -> CatalogItem:
    name = _clean(row.get("Event Name"))
    location = _clean(row.get("Location"))
    entry = _clean(row.get("Entry Fee"))
    return CatalogItem(
        id=f"event_{_slug(name)}_{idx}",
        type="event",
        name=name or "Unknown event",
        city=location,
        subtype=_clean(row.get("Type of Event")),
        description=_clean(row.get("Description")),
        event_date=_clean(row.get("StartDate")),
        event_duration=_clean(row.get("Duration")),
        audience=_clean(row.get("Target Audience")),
        organizer=_clean(row.get("Organizer")),
        entry_fee=entry,
        currency="EGP" if entry and "free" not in entry.lower() else "FREE",
    )


def _row_medical(row: pd.Series, idx: int) -> CatalogItem:
    facility = _clean(row.get("Facility Name"))
    city = _clean(row.get("City"))
    return CatalogItem(
        id=f"medical_{_slug(facility)}_{_slug(city)}_{idx}",
        type="medical",
        name=facility or "Unknown facility",
        city=city,
        subtype="medical tourism",
        services=_split_list(row.get("Services Offered")),
        description=_clean(row.get("Additional Information")),
        price_category=_clean(row.get("Price_category")),
        entry_fee=_clean(row.get("Approximate Prices (EGP)")),
        currency="EGP",
    )


# ── CSV reader (encoding-tolerant) ────────────────────────────────────────────
def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Optional[Exception] = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=enc)
            df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]
            return df
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return pd.DataFrame()


# ── Catalog loader (cached) ───────────────────────────────────────────────────
_FILE_REGISTRY: list[tuple[str, callable]] = [
    ("FINAL _Atrreaction dataset.csv", _row_attraction),
    ("egypt_hotels_completed.csv", _row_hotel),
    ("Egypt_Restaurants.csv", _row_restaurant),
    ("Egypt_Transportation_Realistic_Expanded.csv", _row_transport),
    ("flights_data_egypt_with_realistic_prices.csv", _row_flight),
    ("events.csv", _row_event),
]
_MEDICAL_XLSX = "medical_tourism_prices_egp_converted.xlsx"


@lru_cache(maxsize=1)
def load_catalog() -> List[CatalogItem]:
    """Read every source file once and return the full catalog list."""
    base = settings.egypt_csv_dir
    items: List[CatalogItem] = []
    for filename, converter in _FILE_REGISTRY:
        path = base / filename
        if not path.exists():
            logger.warning("[catalog] missing CSV: %s", path.name)
            continue
        df = _read_csv(path)
        for idx, row in df.iterrows():
            try:
                items.append(converter(row, int(idx)))
            except Exception as exc:  # noqa: BLE001
                logger.warning("[catalog] %s row %d failed: %s", path.name, idx, exc)
        logger.info("[catalog] loaded %d items from %s", len(df), path.name)

    medical_path = base / _MEDICAL_XLSX
    if medical_path.exists():
        df = pd.read_excel(medical_path, dtype=str).fillna("")
        df.columns = [c.strip() for c in df.columns]
        for idx, row in df.iterrows():
            try:
                items.append(_row_medical(row, int(idx)))
            except Exception as exc:  # noqa: BLE001
                logger.warning("[catalog] medical row %d failed: %s", idx, exc)
        logger.info("[catalog] loaded %d items from %s", len(df), medical_path.name)

    # Filter out excluded types (e.g. flight — app is domestic Egypt only)
    items = [it for it in items if it.type not in _EXCLUDED_TYPES]
    logger.info("[catalog] total items after filtering: %d", len(items))
    return items


@lru_cache(maxsize=1)
def by_type() -> Dict[CatalogType, List[CatalogItem]]:
    bucket: Dict[CatalogType, List[CatalogItem]] = {}
    for it in load_catalog():
        bucket.setdefault(it.type, []).append(it)
    return bucket


def by_id(item_id: str) -> Optional[CatalogItem]:
    for it in load_catalog():
        if it.id == item_id:
            return it
    return None


# ── Query helpers ─────────────────────────────────────────────────────────────
_SEASON_BY_MONTH = {
    1: ("January", "winter"),
    2: ("February", "winter"),
    3: ("March", "spring"),
    4: ("April", "spring"),
    5: ("May", "spring"),
    6: ("June", "summer"),
    7: ("July", "summer"),
    8: ("August", "summer"),
    9: ("September", "fall"),
    10: ("October", "fall"),
    11: ("November", "fall"),
    12: ("December", "winter"),
}

_SEASON_TO_MONTHS = {
    "winter": {12, 1, 2},
    "spring": {3, 4, 5},
    "summer": {6, 7, 8},
    "fall": {9, 10, 11},
    "autumn": {9, 10, 11},
}

_MONTH_NAMES = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}


def _months_from_best_season(text: str) -> set[int]:
    """Parse strings like ``September to November`` or ``Winter`` → set of months."""
    t = (text or "").lower()
    if not t:
        return set()
    months: set[int] = set()
    # Direct season words
    for name, ms in _SEASON_TO_MONTHS.items():
        if name in t:
            months |= ms
    # Month ranges: "September to November", "Sep - Nov", "December to February"
    range_match = re.search(
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june|jun|"
        r"july|jul|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s*(?:to|-|–|—|until)\s*"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june|jun|"
        r"july|jul|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)",
        t,
    )
    if range_match:
        a = _MONTH_NAMES.get(range_match.group(1))
        b = _MONTH_NAMES.get(range_match.group(2))
        if a and b:
            i = a
            while True:
                months.add(i)
                if i == b:
                    break
                i = 1 if i == 12 else i + 1
    # Single month mentions
    for word, m in _MONTH_NAMES.items():
        if re.search(rf"\b{word}\b", t):
            months.add(m)
    return months


def current_month() -> int:
    return datetime.utcnow().month


def in_current_season(item: CatalogItem, month: Optional[int] = None) -> bool:
    """True if ``item.best_season`` overlaps with the given month (default: now)."""
    if not item.best_season:
        return False
    m = month or current_month()
    months = _months_from_best_season(item.best_season)
    return m in months if months else False


_OFF_PEAK_PATTERNS = [
    r"early\s*morning",
    r"\b(?:before|prior to)\s*\d+\s*(?:am|a\.m\.)",
    r"\b(?:after)\s*(?:7|8|9|10)\s*(?:pm|p\.m\.)",
    r"\bevening\b",
    r"\bnight\b",
    r"\bsunset\b",
    r"\bweekday",
    r"\b(?:before|after)\s*sunset",
]


def is_off_peak(item: CatalogItem) -> bool:
    """Heuristic: does this attraction have explicit non-midday timing?"""
    t = (item.best_hours or "").lower()
    if not t:
        return False
    return any(re.search(p, t) for p in _OFF_PEAK_PATTERNS)


def is_hot_offer(item: CatalogItem) -> bool:
    """Hotel < 2500 EGP with rating >= 4.0, or 'cheap' medical facility."""
    if item.type == "hotel":
        return (item.price_egp is not None and item.price_egp < 2500
                and (item.rating or 0) >= 4.0)
    if item.type == "medical":
        return (item.price_category or "").lower() in ("cheap", "logical")
    if item.type == "event":
        ef = (item.entry_fee or "").lower()
        return "free" in ef or ef in ("0", "0 egp", "0egp")
    return False


def upcoming_events(month: Optional[int] = None, limit: int = 12) -> List[CatalogItem]:
    """Events whose StartDate matches the current month, sorted soonest-first."""
    target = month or current_month()
    events = by_type().get("event", [])

    def event_month(it: CatalogItem) -> Optional[int]:
        s = it.event_date.strip()
        # Try common formats: "January 7", "2025-01-07", "7/1", "Jan 7"
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%B %d", "%b %d", "%d %B", "%d %b"):
            try:
                return datetime.strptime(s, fmt).month
            except ValueError:
                pass
        for word, m in _MONTH_NAMES.items():
            if re.search(rf"\b{word}\b", s.lower()):
                return m
        return None

    matching: List[Tuple[int, CatalogItem]] = []
    for it in events:
        m = event_month(it)
        if m is None:
            continue
        # rank: prefer this month, then next 3 months wrapping
        delta = (m - target) % 12
        matching.append((delta, it))
    matching.sort(key=lambda x: x[0])
    return [it for _, it in matching[:limit]]


def popular_attractions(min_rating: float = 4.5, limit: int = 12) -> List[CatalogItem]:
    items = [it for it in by_type().get("attraction", []) if (it.rating or 0) >= min_rating]
    items.sort(key=lambda it: (it.rating or 0), reverse=True)
    return items[:limit]


def best_now(month: Optional[int] = None, limit: int = 12) -> List[CatalogItem]:
    items = [it for it in by_type().get("attraction", []) if in_current_season(it, month)]
    items.sort(key=lambda it: (it.rating or 0), reverse=True)
    return items[:limit]


def off_peak_picks(limit: int = 12) -> List[CatalogItem]:
    items = [it for it in by_type().get("attraction", []) if is_off_peak(it)]
    items.sort(key=lambda it: (it.rating or 0), reverse=True)
    return items[:limit]


def hot_offers(limit: int = 12) -> List[CatalogItem]:
    pool: List[CatalogItem] = []
    pool.extend(it for it in by_type().get("hotel", []) if is_hot_offer(it))
    pool.extend(it for it in by_type().get("medical", []) if is_hot_offer(it))
    pool.extend(it for it in by_type().get("event", []) if is_hot_offer(it))
    pool.sort(key=lambda it: (it.rating or 0), reverse=True)
    return pool[:limit]


def featured_hotels(min_rating: float = 4.5, limit: int = 12) -> List[CatalogItem]:
    items = [it for it in by_type().get("hotel", []) if (it.rating or 0) >= min_rating]
    items.sort(key=lambda it: (it.rating or 0), reverse=True)
    return items[:limit]


def local_food(min_rating: float = 4.5, limit: int = 12) -> List[CatalogItem]:
    items = [it for it in by_type().get("restaurant", []) if (it.rating or 0) >= min_rating]
    items.sort(key=lambda it: (it.rating or 0), reverse=True)
    return items[:limit]


def by_city(city: str, types: Optional[Iterable[CatalogType]] = None, limit: int = 50) -> List[CatalogItem]:
    target = city.lower().strip()
    out: List[CatalogItem] = []
    for it in load_catalog():
        if types and it.type not in types:
            continue
        if target and target not in it.city.lower():
            continue
        out.append(it)
        if len(out) >= limit:
            break
    return out


def search(query: str, type_filter: Optional[CatalogType] = None, limit: int = 30) -> List[CatalogItem]:
    """Lightweight keyword search across name, city, subtype, description, dishes, services."""
    q = query.strip().lower()
    if not q:
        return []

    def score(item: CatalogItem) -> int:
        s = 0
        if q in item.name.lower():
            s += 5
        if q in item.city.lower():
            s += 3
        if q in (item.subtype or "").lower():
            s += 3
        if q in (item.cuisine or "").lower():
            s += 3
        if any(q in d.lower() for d in item.dishes):
            s += 2
        if any(q in d.lower() for d in item.services):
            s += 2
        if q in (item.description or "").lower():
            s += 1
        if q in (item.organizer or "").lower():
            s += 1
        if q in (item.airline or "").lower():
            s += 2
        if q in (item.transport_mode or "").lower():
            s += 2
        return s

    results: List[Tuple[int, CatalogItem]] = []
    for it in load_catalog():
        if type_filter and it.type != type_filter:
            continue
        sc = score(it)
        if sc > 0:
            results.append((sc, it))
    results.sort(key=lambda x: (x[0], x[1].rating or 0), reverse=True)
    return [it for _, it in results[:limit]]


def categories() -> Dict[str, List[str]]:
    """Return distinct cities / subtypes for filter dropdowns."""
    cities: set[str] = set()
    cuisines: set[str] = set()
    event_types: set[str] = set()
    attraction_types: set[str] = set()
    transport_modes: set[str] = set()
    for it in load_catalog():
        if it.city:
            cities.add(it.city)
        if it.type == "restaurant" and it.cuisine:
            cuisines.add(it.cuisine)
        if it.type == "event" and it.subtype:
            event_types.add(it.subtype)
        if it.type == "attraction" and it.subtype:
            attraction_types.add(it.subtype)
        if it.type == "transport" and it.transport_mode:
            transport_modes.add(it.transport_mode)
    return {
        "cities": sorted(cities),
        "cuisines": sorted(cuisines),
        "event_types": sorted(event_types),
        "attraction_types": sorted(attraction_types),
        "transport_modes": sorted(transport_modes),
    }


__all__ = [
    "CatalogItem",
    "load_catalog",
    "by_type",
    "by_id",
    "search",
    "categories",
    "current_month",
    "in_current_season",
    "is_off_peak",
    "is_hot_offer",
    "upcoming_events",
    "popular_attractions",
    "best_now",
    "off_peak_picks",
    "hot_offers",
    "featured_hotels",
    "local_food",
    "by_city",
]
