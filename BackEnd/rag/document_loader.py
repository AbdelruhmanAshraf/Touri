"""
Egypt dataset → semantic Markdown loader.

For Phase 1 we baseline on Egypt. Each row in the source CSV/XLSX files
becomes one descriptive Markdown block (heading + bullet facts + tags) that
is friendly to both an embedding model and an LLM reader.

Public surface
--------------
``Document``                 typed payload used by the vector store.
``load_all_egypt_documents`` ingest every Egypt file in ``settings.egypt_csv_dir``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)


# ── Document type ─────────────────────────────────────────────────────────────
@dataclass
class Document:
    """A single semantic chunk ready for embedding."""

    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _slug(value: str) -> str:
    """Lowercase ASCII slug for stable IDs."""
    value = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip().lower())
    return value.strip("_") or "unknown"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() in ("nan", "none", "null") else s


def _bullet(label: str, value: Any) -> str | None:
    v = _clean(value)
    return f"- **{label}:** {v}" if v else None


def _block(
    *,
    heading: str,
    bullets: Iterable[str | None],
    tags: Iterable[str] = (),
    body: str = "",
) -> str:
    """Compose the Markdown block."""
    lines = [f"# {heading}"]
    lines.extend(b for b in bullets if b)
    if body:
        lines.append("")
        lines.append(body.strip())
    if tags:
        lines.append("")
        lines.append("Tags: " + ", ".join(sorted({t for t in tags if t})))
    return "\n".join(lines).strip()


def _read_csv(path: Path) -> pd.DataFrame:
    """Robust CSV reader: handles BOM + Windows-1252 + odd column whitespace."""
    last_error: Exception | None = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=enc)
            df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]
            return df
        except UnicodeDecodeError as exc:  # try the next encoding
            last_error = exc
    raise last_error  # type: ignore[misc]


# ── Per-domain row → Document converters ──────────────────────────────────────
def _hotel_row(row: pd.Series, idx: int) -> Document:
    name = _clean(row.get("Hotel Name"))
    city = _clean(row.get("City"))
    amenities = _clean(row.get("Amenities"))
    price = _clean(row.get("Price (EGP)"))
    rating = _clean(row.get("Rating"))
    text = _block(
        heading=f"Hotel: {name or 'Unknown'} ({city})",
        bullets=[
            _bullet("City", city),
            _bullet("Nightly price (EGP)", price),
            _bullet("Guest rating", rating),
            _bullet("Amenities", amenities),
        ],
        tags=["hotel", "accommodation", city.lower(), "egypt"],
    )
    return Document(
        id=f"hotel_{_slug(name)}_{_slug(city)}_{idx}",
        text=text,
        metadata={
            "domain": "hotel",
            "name": name,
            "city": city,
            "price_egp": price,
            "rating": rating,
        },
    )


def _restaurant_row(row: pd.Series, idx: int) -> Document:
    name = _clean(row.get("Name"))
    city = _clean(row.get("City"))
    text = _block(
        heading=f"Restaurant: {name or 'Unknown'} ({city})",
        bullets=[
            _bullet("City", city),
            _bullet("Cuisine", row.get("Cuisine Type")),
            _bullet("Signature dishes", row.get("Specialty Dishes")),
            _bullet("Price range", row.get("Price Range")),
            _bullet("Dietary options", row.get("Dietary Options")),
            _bullet("Rating", row.get("User Rating")),
            _bullet("Reviewer notes", row.get("Reviews")),
            _bullet("Map link", row.get("Google Maps Link")),
        ],
        tags=["restaurant", "food", city.lower(), "egypt"],
    )
    return Document(
        id=f"restaurant_{_slug(name)}_{_slug(city)}_{idx}",
        text=text,
        metadata={
            "domain": "restaurant",
            "name": name,
            "city": city,
            "cuisine": _clean(row.get("Cuisine Type")),
            "rating": _clean(row.get("User Rating")),
        },
    )


def _transport_row(row: pd.Series, idx: int) -> Document:
    frm = _clean(row.get("From_Province"))
    to = _clean(row.get("To_Province"))
    mode = _clean(row.get("Transport_Type"))
    text = _block(
        heading=f"Transport: {frm} → {to} ({mode})",
        bullets=[
            _bullet("Mode", mode),
            _bullet("From", frm),
            _bullet("To", to),
            _bullet("Operator", row.get("Company_Name")),
            _bullet("Avg price (EGP)", row.get("Avg_Price_EGP")),
            _bullet("Distance (km)", row.get("Distance_KM")),
            _bullet("Avg duration (h)", row.get("Avg_Duration_Hours")),
            _bullet("Frequency", row.get("Frequency")),
            _bullet("Notes", row.get("Notes")),
        ],
        tags=["transport", mode.lower(), frm.lower(), to.lower(), "egypt"],
    )
    return Document(
        id=f"transport_{_slug(frm)}_{_slug(to)}_{_slug(mode)}_{idx}",
        text=text,
        metadata={
            "domain": "transport",
            "mode": mode,
            "from": frm,
            "to": to,
            "price_egp": _clean(row.get("Avg_Price_EGP")),
        },
    )


def _event_row(row: pd.Series, idx: int) -> Document:
    name = _clean(row.get("Event Name"))
    location = _clean(row.get("Location"))
    text = _block(
        heading=f"Event: {name or 'Unknown'}",
        bullets=[
            _bullet("Location", location),
            _bullet("Start date", row.get("StartDate")),
            _bullet("Duration", row.get("Duration")),
            _bullet("Type", row.get("Type of Event")),
            _bullet("Audience", row.get("Target Audience")),
            _bullet("Entry fee", row.get("Entry Fee")),
            _bullet("Organizer", row.get("Organizer")),
        ],
        body=_clean(row.get("Description")),
        tags=["event", _clean(row.get("Type of Event")).lower(), location.lower(), "egypt"],
    )
    return Document(
        id=f"event_{_slug(name)}_{idx}",
        text=text,
        metadata={
            "domain": "event",
            "name": name,
            "location": location,
            "type": _clean(row.get("Type of Event")),
            "start_date": _clean(row.get("StartDate")),
        },
    )


def _attraction_row(row: pd.Series, idx: int) -> Document:
    name = _clean(row.get("Attraction"))
    city = _clean(row.get("City"))
    text = _block(
        heading=f"Attraction: {name or 'Unknown'} ({city})",
        bullets=[
            _bullet("City", city),
            _bullet("Type", row.get("Type")),
            _bullet("Rating", row.get("Rating")),
            _bullet("Best season", row.get("Best time to visit")),
            _bullet("Best hours", row.get("Best hour to visit")),
            _bullet("Entry fee", row.get("Entry fee")),
            _bullet("Distance from Cairo (km)", row.get("Distance from Cairo (km)")),
            _bullet("Map link", row.get("Location")),
        ],
        body=_clean(row.get("Description")),
        tags=["attraction", _clean(row.get("Type")).lower(), city.lower(), "egypt"],
    )
    return Document(
        id=f"attraction_{_slug(name)}_{_slug(city)}_{idx}",
        text=text,
        metadata={
            "domain": "attraction",
            "name": name,
            "city": city,
            "type": _clean(row.get("Type")),
            "rating": _clean(row.get("Rating")),
        },
    )


def _flight_row(row: pd.Series, idx: int) -> Document:
    frm, to = _clean(row.get("From")), _clean(row.get("To"))
    airline = _clean(row.get("Airline"))
    text = _block(
        heading=f"Flight: {frm} → {to} on {airline}",
        bullets=[
            _bullet("Origin", frm),
            _bullet("Destination", to),
            _bullet("Airline", airline),
            _bullet("Class", row.get("Class")),
            _bullet("Price (USD)", row.get("Price (USD)")),
            _bullet("Duration (min)", row.get("Flight Duration (Minutes)")),
            _bullet("Weekly flights", row.get("Weekly Flights")),
            _bullet("Stops", row.get("Stops")),
            _bullet("Departure date", row.get("Departure Date")),
            _bullet("Booking link", row.get("Airline Link")),
        ],
        tags=["flight", airline.lower(), frm.lower(), to.lower(), "egypt"],
    )
    return Document(
        id=f"flight_{_slug(frm)}_{_slug(to)}_{_slug(airline)}_{idx}",
        text=text,
        metadata={
            "domain": "flight",
            "from": frm,
            "to": to,
            "airline": airline,
            "price_usd": _clean(row.get("Price (USD)")),
        },
    )


def _medical_row(row: pd.Series, idx: int) -> Document:
    facility = _clean(row.get("Facility Name"))
    city = _clean(row.get("City"))
    text = _block(
        heading=f"Medical facility: {facility} ({city})",
        bullets=[
            _bullet("City", city),
            _bullet("Services offered", row.get("Services Offered")),
            _bullet("Approximate prices (EGP)", row.get("Approximate Prices (EGP)")),
            _bullet("Price category", row.get("Price_category")),
        ],
        body=_clean(row.get("Additional Information")),
        tags=["medical", "tourism", "healthcare", city.lower(), "egypt"],
    )
    return Document(
        id=f"medical_{_slug(facility)}_{_slug(city)}_{idx}",
        text=text,
        metadata={
            "domain": "medical",
            "facility": facility,
            "city": city,
            "price_category": _clean(row.get("Price_category")),
        },
    )


# ── File registry ─────────────────────────────────────────────────────────────
RowConverter = Callable[[pd.Series, int], Document]

_FILE_REGISTRY: list[tuple[str, RowConverter]] = [
    ("egypt_hotels_completed.csv", _hotel_row),
    ("Egypt_Restaurants.csv", _restaurant_row),
    ("Egypt_Transportation_Realistic_Expanded.csv", _transport_row),
    ("events.csv", _event_row),
    # Note: stray leading space in original filename is intentional.
    ("FINAL _Atrreaction dataset.csv", _attraction_row),
    ("flights_data_egypt_with_realistic_prices.csv", _flight_row),
]
_MEDICAL_XLSX = "medical_tourism_prices_egp_converted.xlsx"


def _load_file(path: Path, row_fn: RowConverter) -> List[Document]:
    if not path.exists():
        logger.warning("[loader] missing CSV: %s", path.name)
        return []
    df = _read_csv(path)
    docs: list[Document] = []
    for idx, row in df.iterrows():
        try:
            docs.append(row_fn(row, int(idx)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[loader] %s row %d failed: %s", path.name, idx, exc)
    logger.info("[loader] %s → %d docs", path.name, len(docs))
    return docs


def _load_medical(path: Path) -> List[Document]:
    if not path.exists():
        logger.warning("[loader] missing XLSX: %s", path.name)
        return []
    df = pd.read_excel(path, dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    docs = [_medical_row(row, idx) for idx, row in df.iterrows()]
    logger.info("[loader] %s → %d docs", path.name, len(docs))
    return docs


def load_all_egypt_documents() -> List[Document]:
    """Read every Egypt source file and return Markdown ``Document`` chunks."""
    base = settings.egypt_csv_dir
    docs: list[Document] = []
    for filename, converter in _FILE_REGISTRY:
        docs.extend(_load_file(base / filename, converter))
    docs.extend(_load_medical(base / _MEDICAL_XLSX))
    logger.info("[loader] total Egypt documents: %d", len(docs))
    return docs


__all__ = ["Document", "load_all_egypt_documents"]
