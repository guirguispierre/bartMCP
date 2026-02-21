import os
import httpx
from fastmcp import FastMCP

BART_API_KEY = os.environ.get("BART_API_KEY", "MW9S-E7SL-26DU-VV8V")
BART_BASE = "https://api.bart.gov/api"

mcp = FastMCP("bart-mcp-server")

# ---------------------------------------------------------------------------
# Station name → abbreviation lookup
# ---------------------------------------------------------------------------
STATION_MAP = {
    "antioch": "ANTC",
    "pittsburg center": "PCTR",
    "pittsburg bay point": "PITT",
    "north concord": "NCON",
    "concord": "CONC",
    "pleasant hill": "PHIL",
    "walnut creek": "WCRK",
    "lafayette": "LAFY",
    "orinda": "ORIN",
    "rockridge": "ROCK",
    "macarthur": "MCAR",
    "mac arthur": "MCAR",
    "19th street": "19TH",
    "12th street": "12TH",
    "daly city": "DALY",
    "colma": "COLM",
    "south san francisco": "SSAN",
    "san bruno": "SBRN",
    "millbrae": "MLBR",
    "san francisco airport": "SFIA",
    "sfo": "SFIA",
    "west oakland": "WOAK",
    "lake merritt": "LAKE",
    "fruitvale": "FTVL",
    "coliseum": "COLS",
    "san leandro": "SANL",
    "bay fair": "BAYF",
    "castro valley": "CAST",
    "west dublin": "WDUB",
    "dublin pleasanton": "DUBL",
    "dublin": "DUBL",
    "pleasanton": "DUBL",
    "union city": "UCTY",
    "fremont": "FRMT",
    "south fremont": "SHAY",
    "warm springs": "WARM",
    "milpitas": "MLPT",
    "berryessa": "BERY",
    "ashby": "ASHB",
    "downtown berkeley": "DBRK",
    "berkeley": "DBRK",
    "north berkeley": "NBRK",
    "el cerrito plaza": "PLZA",
    "el cerrito del norte": "DELN",
    "richmond": "RICH",
    "embarcadero": "EMBR",
    "montgomery": "MONT",
    "powell": "POWL",
    "civic center": "CIVC",
    "16th mission": "16TH",
    "24th mission": "24TH",
    "glen park": "GLEN",
    "balboa park": "BALB",
    "oakland airport": "OAKL",
    "oak": "OAKL",
}

LINE_COLORS = {"yellow", "red", "orange", "green", "blue", "beige"}


def resolve_station(name: str) -> str:
    """Convert a station name or abbreviation to a BART abbreviation."""
    stripped = name.strip()
    # Already looks like an abbreviation
    if stripped.upper() == stripped and 2 <= len(stripped) <= 5:
        return stripped.upper()
    lower = stripped.lower()
    if lower in STATION_MAP:
        return STATION_MAP[lower]
    # Fuzzy: find first key containing the input or vice versa
    for key, abbr in STATION_MAP.items():
        if key in lower or lower in key:
            return abbr
    return stripped.upper()


async def bart_get(endpoint: str, params: dict) -> dict:
    """Make a GET request to the BART API and return JSON."""
    params = {"key": BART_API_KEY, "json": "y", **params}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BART_BASE}/{endpoint}", params=params)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool
async def bart_get_departures(station: str, platform: str = "") -> str:
    """
    Get real-time BART departure times from a station.

    Returns the next trains grouped by destination with minutes until departure,
    number of cars, line color, and any delays.

    Args:
        station: Station name (e.g. "Antioch", "Daly City", "Embarcadero") or 4-letter abbreviation (e.g. "ANTC")
        platform: Optional platform number 1-4 to filter by

    Examples:
        - "When is the next BART from Antioch?" → station="Antioch"
        - "Departures from Embarcadero?" → station="Embarcadero"
    """
    abbr = resolve_station(station)
    params = {"cmd": "etd", "orig": abbr}
    if platform:
        params["plat"] = platform

    data = await bart_get("etd.aspx", params)
    station_data = data.get("root", {}).get("station", [None])[0]

    if not station_data:
        return f'No departure data found for "{station}" (tried abbreviation {abbr}). Double-check the station name.'

    time_str = data["root"].get("time", "")
    etds = station_data.get("etd", [])

    if not etds:
        return f"No upcoming departures at {station_data['name']} right now."

    lines = []
    for etd in etds:
        estimates = etd.get("estimate", [])[:3]
        times = []
        for e in estimates:
            mins = e["minutes"]
            label = "🚨 Leaving now" if mins == "Leaving" else f"{mins} min"
            delay = f", ⚠️ {e['delay']}s delay" if e.get("delay", "0") != "0" else ""
            times.append(f"{label} ({e['length']} cars, {e['color']}{delay})")
        lines.append(f"→ {etd['destination']}: {' | '.join(times)}")

    return f"Real-time departures from {station_data['name']} (as of {time_str})\n\n" + "\n".join(lines)


@mcp.tool
async def bart_get_departures_by_line(station: str, line_color: str) -> str:
    """
    Get real-time BART departures filtered by line color.

    Use this when someone asks about a specific colored line, like
    "when is the Yellow Line coming" or "next Orange train".

    Args:
        station: Station name or abbreviation
        line_color: Line color — one of: yellow, red, orange, green, blue, beige

    Examples:
        - "When is the Yellow Line at Antioch?" → station="Antioch", line_color="yellow"
        - "Next orange train at MacArthur?" → station="MacArthur", line_color="orange"
    """
    abbr = resolve_station(station)
    color_upper = line_color.upper()

    data = await bart_get("etd.aspx", {"cmd": "etd", "orig": abbr})
    station_data = data.get("root", {}).get("station", [None])[0]

    if not station_data:
        return f'Station "{station}" not found.'

    matching = []
    for etd in station_data.get("etd", []):
        color_estimates = [e for e in etd.get("estimate", []) if e["color"].upper() == color_upper]
        if color_estimates:
            times = []
            for e in color_estimates[:3]:
                mins = e["minutes"]
                label = "🚨 Leaving now" if mins == "Leaving" else f"{mins} min"
                delay = ", ⚠️ delayed" if e.get("delay", "0") != "0" else ""
                times.append(f"{label} ({e['length']} cars{delay})")
            matching.append(f"→ {etd['destination']}: {' | '.join(times)}")

    if not matching:
        return f"No {line_color} line trains currently departing from {station_data['name']}."

    return f"{line_color.title()} Line departures from {station_data['name']}:\n\n" + "\n".join(matching)


@mcp.tool
async def bart_get_departures_to_destination(origin: str, destination: str) -> str:
    """
    Get real-time BART trains from one station heading toward a specific destination.

    Use for questions like "next train from MacArthur to Antioch" or
    "trains from Embarcadero to Daly City".

    Args:
        origin: Origin station name or abbreviation
        destination: Target destination station name or abbreviation
    """
    orig_abbr = resolve_station(origin)
    dest_lower = destination.lower().strip()

    data = await bart_get("etd.aspx", {"cmd": "etd", "orig": orig_abbr})
    station_data = data.get("root", {}).get("station", [None])[0]

    if not station_data:
        return f'Station "{origin}" not found.'

    matching = []
    for etd in station_data.get("etd", []):
        dest_name = etd["destination"].lower()
        dest_abbr = etd.get("abbreviation", "").lower()
        if dest_lower in dest_name or dest_name in dest_lower or dest_lower == dest_abbr:
            times = [
                ("🚨 Now" if e["minutes"] == "Leaving" else f"{e['minutes']} min")
                for e in etd.get("estimate", [])[:3]
            ]
            matching.append(f"→ {etd['destination']}: {', '.join(times)}")

    if not matching:
        all_dests = ", ".join(e["destination"] for e in station_data.get("etd", []))
        return (
            f'No direct trains to "{destination}" from {station_data["name"]}.\n\n'
            f"Available destinations: {all_dests}\n\n"
            "Try bart_get_trip for multi-leg trips with transfers."
        )

    return f"Trains from {station_data['name']} toward {destination}:\n\n" + "\n".join(matching)


@mcp.tool
async def bart_get_trip(origin: str, destination: str, time: str = "now", date: str = "today") -> str:
    """
    Plan a BART trip between two stations with full route, timing, and fare info.

    Use for questions like "How do I get from Antioch to SFO?" or
    "Plan my BART trip from Fremont to Embarcadero."

    Args:
        origin: Departure station name or abbreviation
        destination: Arrival station name or abbreviation
        time: Departure time in HH:MM format (default: now)
        date: Date in MM/DD/YYYY format (default: today)
    """
    orig_abbr = resolve_station(origin)
    dest_abbr = resolve_station(destination)

    data = await bart_get("sched.aspx", {
        "cmd": "depart",
        "orig": orig_abbr,
        "dest": dest_abbr,
        "time": time,
        "date": date,
        "b": "2",
        "a": "3",
    })

    trips = data.get("root", {}).get("schedule", {}).get("request", {}).get("trip", [])
    if not trips:
        return f'No trips found from "{origin}" to "{destination}".'

    lines = []
    for i, trip in enumerate(trips[:3], 1):
        legs = trip.get("leg", [])
        if isinstance(legs, dict):
            legs = [legs]

        leg_desc = "\n".join(
            f"  {leg['origStation']} → {leg['destStation']} ({leg.get('line','?')}, dep {leg['origTimeMin']}, arr {leg['destTimeMin']})"
            for leg in legs
        )

        fares = trip.get("fares", {}).get("fare", [])
        clipper = next((f["amount"] for f in fares if f.get("class") == "clipper"), None)
        cash = next((f["amount"] for f in fares if f.get("class") == "normal"), None)
        fare_str = f"Clipper: ${clipper}" if clipper else (f"Cash: ${cash}" if cash else "Fare: N/A")

        lines.append(
            f"Option {i}: Depart {trip['origTimeMin']} → Arrive {trip['destTimeMin']} ({trip.get('tripTime','?')} min) | {fare_str}\n{leg_desc}"
        )

    return f"BART Trip: {orig_abbr} → {dest_abbr}\n\n" + "\n\n".join(lines)


@mcp.tool
async def bart_get_fare(origin: str, destination: str) -> str:
    """
    Get the ticket fare between two BART stations.

    Returns both Clipper card and cash prices.

    Args:
        origin: Origin station name or abbreviation
        destination: Destination station name or abbreviation

    Examples:
        - "How much does BART cost from Embarcadero to SFO?"
        - "BART fare Antioch to Fremont"
    """
    orig_abbr = resolve_station(origin)
    dest_abbr = resolve_station(destination)

    data = await bart_get("sched.aspx", {"cmd": "fare", "orig": orig_abbr, "dest": dest_abbr})
    fares = data.get("root", {}).get("fares", {}).get("fare", [])

    clipper = next((f["amount"] for f in fares if f.get("class") == "clipper"), "N/A")
    cash = next((f["amount"] for f in fares if f.get("class") == "normal"), "N/A")

    return f"BART Fare: {orig_abbr} → {dest_abbr}\n\n💳 Clipper: ${clipper}\n💵 Cash: ${cash}"


@mcp.tool
async def bart_get_advisories(station: str = "") -> str:
    """
    Get current BART service advisories, delays, and alerts.

    Use for questions like "Is BART running normally?", "Any BART delays today?",
    or "What's happening with BART service?"

    Args:
        station: Optional station name to filter advisories. Leave blank for system-wide alerts.
    """
    params = {"cmd": "bsa"}
    if station:
        params["orig"] = resolve_station(station)

    data = await bart_get("bsa.aspx", params)
    root = data.get("root", {})
    bsa_raw = root.get("bsa", [])
    advisories = bsa_raw if isinstance(bsa_raw, list) else ([bsa_raw] if bsa_raw else [])

    if not advisories:
        return "✅ No current BART service advisories. Trains are running normally."

    lines = []
    for a in advisories:
        desc = (
            a.get("description", {}).get("#cdata-section")
            or a.get("sms_text", {}).get("#cdata-section")
            or "No description available"
        )
        station_label = "System-wide" if a.get("station") == "BART" else a.get("station", "Unknown")
        lines.append(f"⚠️ {a.get('type','Alert')} ({station_label}): {desc}")

    time_str = root.get("time", "")
    return f"BART Service Advisories ({time_str})\n\n" + "\n\n".join(lines)


@mcp.tool
async def bart_get_elevator_status() -> str:
    """
    Get current BART elevator outages across all stations.

    Useful for accessibility planning. Returns which stations have elevator issues.
    """
    data = await bart_get("bsa.aspx", {"cmd": "elev"})
    root = data.get("root", {})
    bsa_raw = root.get("bsa", [])
    elevators = bsa_raw if isinstance(bsa_raw, list) else ([bsa_raw] if bsa_raw else [])

    if not elevators:
        return "✅ All BART elevators are currently operating normally."

    lines = []
    for e in elevators:
        desc = e.get("description", {}).get("#cdata-section", "No description")
        lines.append(f"🛗 {e.get('station','Unknown')}: {desc}")

    return f"BART Elevator Status ({root.get('time','')})\n\n" + "\n\n".join(lines)


@mcp.tool
async def bart_list_stations() -> str:
    """
    List all BART stations with their names, abbreviations, and cities.

    Use when you need to find the correct station name or abbreviation,
    or when someone asks "what BART stations are there?"
    """
    data = await bart_get("stn.aspx", {"cmd": "stns"})
    stations = data.get("root", {}).get("stations", {}).get("station", [])

    lines = [f"{s['abbr']} — {s['name']} ({s['city']})" for s in stations]
    return f"All BART Stations ({len(stations)} total)\n\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse

    async def health(request):
        return JSONResponse({"status": "ok", "service": "bart-mcp-server"})

    # Get the ASGI app from FastMCP for streamable HTTP
    mcp_app = mcp.http_app(path="/mcp")

    app = Starlette(routes=[
        Route("/health", health),
        Mount("/", app=mcp_app),
    ])

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
