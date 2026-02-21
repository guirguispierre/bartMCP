# bart-mcp-server 🚊

A [FastMCP](https://github.com/jlowin/fastmcp) server that gives **Poke.com** real-time BART transit data.

Ask Poke things like:
- *"When is the next train from Antioch?"*
- *"When is the Yellow Line arriving at MacArthur?"*
- *"How much does BART cost from Embarcadero to SFO?"*
- *"Are there any BART delays right now?"*
- *"Plan a trip from Fremont to Daly City"*

---

## Tools

| Tool | What it does |
|------|-------------|
| `bart_get_departures` | Real-time departures from any station |
| `bart_get_departures_by_line` | Filter by line color (Yellow, Red, Orange, etc.) |
| `bart_get_departures_to_destination` | Trains heading toward a specific station |
| `bart_get_trip` | Full trip planner with transfers and fares |
| `bart_get_fare` | Clipper + cash price between two stations |
| `bart_get_advisories` | System-wide or station-specific service alerts |
| `bart_get_elevator_status` | Elevator outages for accessibility planning |
| `bart_list_stations` | All BART stations with abbreviations |

---

## Deploy to Render (for Poke.com)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/guirguispierre/bartMCP)

1. Click the button above
2. Set the `BART_API_KEY` environment variable (get a free key at [api.bart.gov/api/register.aspx](https://api.bart.gov/api/register.aspx))
3. Deploy — your MCP endpoint will be at `https://your-service.onrender.com/mcp`

### Add to Poke.com

Go to [poke.com/settings/connections/integrations/new](https://poke.com/settings/connections/integrations/new) and enter your Render URL.

Then text Poke: *"When is the next Yellow Line at MacArthur?"* 🚊

---

## Local Development

```bash
git clone https://github.com/guirguispierre/bartMCP.git
cd bartMCP
pip install -r requirements.txt

export BART_API_KEY=your-key-here
python src/server.py
```

Test with MCP Inspector:
```bash
npx @modelcontextprotocol/inspector
# Connect to http://localhost:8000/mcp using Streamable HTTP
```

---

## Station Names

You can use full names or abbreviations — the server handles fuzzy matching:

| Station | Abbr |
|---------|------|
| Antioch | ANTC |
| Daly City | DALY |
| Embarcadero | EMBR |
| Fremont | FRMT |
| Richmond | RICH |
| SFO | SFIA |
| MacArthur | MCAR |

Built with [FastMCP](https://github.com/jlowin/fastmcp) + [BART Legacy API](https://api.bart.gov).
