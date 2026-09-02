"""Explicit, user-triggered address lookup for the Streamlit intake."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = (
    "Ericsson-RF-ROM-UX-Prototype/1.0 "
    "(+https://github.com/AhmedFuzail/AI-Assisted-RF-Coverage---ROM-Estimation-Tool)"
)


def search_address(query, timeout_seconds=5):
    """Return address suggestions and a user-safe error message, if any."""
    normalized_query = str(query or "").strip()
    if len(normalized_query) < 3:
        return [], "Enter at least three characters before searching."

    params = urlencode({
        "q": normalized_query,
        "format": "json",
        "addressdetails": 1,
        "limit": 5,
    })
    request = Request(
        f"{NOMINATIM_SEARCH_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            results = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return [], f"Address service returned HTTP {error.code}. Please try again later."
    except TimeoutError:
        return [], "Address search timed out. Please try again."
    except URLError:
        return [], "Address service is unavailable. Check the network connection and try again."
    except (OSError, json.JSONDecodeError):
        return [], "Address search failed. Please try again or enter coordinates manually."

    if not isinstance(results, list):
        return [], "Address service returned an unexpected response. Please try again later."

    suggestions = []
    for result in results:
        try:
            latitude = float(result["lat"])
            longitude = float(result["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        suggestions.append({
            "label": result.get("display_name", "Unknown address"),
            "latitude": latitude,
            "longitude": longitude,
        })

    if not suggestions:
        return [], "No matching addresses were found. You can enter coordinates manually below."
    return suggestions, None
