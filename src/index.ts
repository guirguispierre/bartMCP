import { createMcpHandler } from "agents/mcp";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

export interface Env {
  BART_API_KEY: string;
}

const STATION_MAP: Record<string, string> = {
  "antioch": "ANTC", "pittsburg center": "PCTR", "pittsburg bay point": "PITT",
  "north concord": "NCON", "concord": "CONC", "pleasant hill": "PHIL",
  "walnut creek": "WCRK", "lafayette": "LAFY", "orinda": "ORIN",
  "rockridge": "ROCK", "macarthur": "MCAR", "mac arthur": "MCAR",
  "19th street": "19TH", "12th street": "12TH", "daly city": "DALY",
  "colma": "COLM", "south san francisco": "SSAN", "san bruno": "SBRN",
  "millbrae": "MLBR", "san francisco airport": "SFIA", "sfo": "SFIA",
  "west oakland": "WOAK", "lake merritt": "LAKE", "fruitvale": "FTVL",
  "coliseum": "COLS", "san leandro": "SANL", "bay fair": "BAYF",
  "castro valley": "CAST", "west dublin": "WDUB", "dublin pleasanton": "DUBL",
  "dublin": "DUBL", "pleasanton": "DUBL", "union city": "UCTY",
  "fremont": "FRMT", "south fremont": "SHAY", "warm springs": "WARM",
  "milpitas": "MLPT", "berryessa": "BERY", "ashby": "ASHB",
  "downtown berkeley": "DBRK", "berkeley": "DBRK", "north berkeley": "NBRK",
  "el cerrito plaza": "PLZA", "el cerrito del norte": "DELN", "richmond": "RICH",
  "embarcadero": "EMBR", "montgomery": "MONT", "powell": "POWL",
  "civic center": "CIVC", "16th mission": "16TH", "24th mission": "24TH",
  "glen park": "GLEN", "balboa park": "BALB", "oakland airport": "OAKL", "oak": "OAKL",
};

function resolveStation(name: string): string {
  const s = name.trim();
  if (s === s.toUpperCase() && s.length >= 2 && s.length <= 5) return s.toUpperCase();
  const lower = s.toLowerCase();
  if (STATION_MAP[lower]) return STATION_MAP[lower];
  for (const [key, abbr] of Object.entries(STATION_MAP)) {
    if (key.includes(lower) || lower.includes(key)) return abbr;
  }
  return s.toUpperCase();
}

async function bartGet(endpoint: string, params: Record<string, string>, apiKey: string): Promise<any> {
  const url = new URL(`https://api.bart.gov/api/${endpoint}`);
  url.searchParams.set("key", apiKey);
  url.searchParams.set("json", "y");
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`BART API error: ${res.status}`);
  return res.json();
}

function buildServer(apiKey: string): McpServer {
  const server = new McpServer({ name: "bart-mcp-server", version: "1.0.0" });

  server.tool("bart_get_departures", "Get real-time BART departure times from a station.",
    { station: z.string(), platform: z.string().optional() },
    async ({ station, platform }) => {
      const abbr = resolveStation(station);
      const params: Record<string, string> = { cmd: "etd", orig: abbr };
      if (platform) params["plat"] = platform;
      const data = await bartGet("etd.aspx", params, apiKey);
      const s = data?.root?.station?.[0];
      if (!s) return { content: [{ type: "text" as const, text: `No data for "${station}" (tried ${abbr}).` }] };
      const etds = s.etd ?? [];
      if (!etds.length) return { content: [{ type: "text" as const, text: `No departures at ${s.name}.` }] };
      const lines = etds.map((etd: any) => {
        const times = (etd.estimate ?? []).slice(0, 3).map((e: any) => {
          const label = e.minutes === "Leaving" ? "🚨 Now" : `${e.minutes} min`;
          const delay = e.delay && e.delay !== "0" ? ` ⚠️` : "";
          return `${label} (${e.length}car ${e.color}${delay})`;
        });
        return `→ ${etd.destination}: ${times.join(" | ")}`;
      });
      return { content: [{ type: "text" as const, text: `Departures from ${s.name} (${data.root?.time ?? ""})\n\n${lines.join("\n")}` }] };
    }
  );

  server.tool("bart_get_departures_by_line", "Get BART departures filtered by line color.",
    { station: z.string(), line_color: z.string() },
    async ({ station, line_color }) => {
      const abbr = resolveStation(station);
      const colorUpper = line_color.toUpperCase();
      const data = await bartGet("etd.aspx", { cmd: "etd", orig: abbr }, apiKey);
      const s = data?.root?.station?.[0];
      if (!s) return { content: [{ type: "text" as const, text: `Station "${station}" not found.` }] };
      const matching: string[] = [];
      for (const etd of s.etd ?? []) {
        const filtered = (etd.estimate ?? []).filter((e: any) => e.color?.toUpperCase() === colorUpper);
        if (filtered.length) {
          const times = filtered.slice(0, 3).map((e: any) =>
            `${e.minutes === "Leaving" ? "🚨 Now" : e.minutes + " min"} (${e.length}car)`
          );
          matching.push(`→ ${etd.destination}: ${times.join(" | ")}`);
        }
      }
      if (!matching.length) return { content: [{ type: "text" as const, text: `No ${line_color} trains at ${s.name}.` }] };
      return { content: [{ type: "text" as const, text: `${line_color} Line from ${s.name}:\n\n${matching.join("\n")}` }] };
    }
  );

  server.tool("bart_get_departures_to_destination", "Get BART trains heading to a specific destination.",
    { origin: z.string(), destination: z.string() },
    async ({ origin, destination }) => {
      const origAbbr = resolveStation(origin);
      const destLower = destination.toLowerCase().trim();
      const data = await bartGet("etd.aspx", { cmd: "etd", orig: origAbbr }, apiKey);
      const s = data?.root?.station?.[0];
      if (!s) return { content: [{ type: "text" as const, text: `Station "${origin}" not found.` }] };
      const matching: string[] = [];
      for (const etd of s.etd ?? []) {
        const dn = etd.destination?.toLowerCase() ?? "";
        const da = etd.abbreviation?.toLowerCase() ?? "";
        if (destLower.includes(dn) || dn.includes(destLower) || destLower === da) {
          const times = (etd.estimate ?? []).slice(0, 3).map((e: any) => e.minutes === "Leaving" ? "🚨 Now" : `${e.minutes} min`);
          matching.push(`→ ${etd.destination}: ${times.join(", ")}`);
        }
      }
      if (!matching.length) {
        const all = (s.etd ?? []).map((e: any) => e.destination).join(", ");
        return { content: [{ type: "text" as const, text: `No direct trains to "${destination}" from ${s.name}.\n\nAvailable: ${all}` }] };
      }
      return { content: [{ type: "text" as const, text: `Trains from ${s.name} → ${destination}:\n\n${matching.join("\n")}` }] };
    }
  );

  server.tool("bart_get_trip", "Plan a BART trip with route, timing, and fare.",
    { origin: z.string(), destination: z.string(), time: z.string().optional().default("now"), date: z.string().optional().default("today") },
    async ({ origin, destination, time, date }) => {
      const origAbbr = resolveStation(origin);
      const destAbbr = resolveStation(destination);
      const data = await bartGet("sched.aspx", { cmd: "depart", orig: origAbbr, dest: destAbbr, time: time ?? "now", date: date ?? "today", b: "2", a: "3" }, apiKey);
      const trips = data?.root?.schedule?.request?.trip ?? [];
      if (!trips.length) return { content: [{ type: "text" as const, text: `No trips found from "${origin}" to "${destination}".` }] };
      const lines: string[] = [];
      for (let i = 0; i < Math.min(3, trips.length); i++) {
        const trip = trips[i];
        let legs = trip.leg ?? [];
        if (!Array.isArray(legs)) legs = [legs];
        const legDesc = legs.map((leg: any) => `  ${leg.origStation} → ${leg.destStation} (${leg.line ?? "?"}, dep ${leg.origTimeMin}, arr ${leg.destTimeMin})`).join("\n");
        const fares: any[] = trip.fares?.fare ?? [];
        const clipper = fares.find((f: any) => f.class === "clipper")?.amount;
        const cash = fares.find((f: any) => f.class === "normal")?.amount;
        lines.push(`Option ${i + 1}: ${trip.origTimeMin} → ${trip.destTimeMin} (${trip.tripTime ?? "?"} min) | ${clipper ? `💳 $${clipper}` : cash ? `💵 $${cash}` : "N/A"}\n${legDesc}`);
      }
      return { content: [{ type: "text" as const, text: `BART Trip: ${origAbbr} → ${destAbbr}\n\n${lines.join("\n\n")}` }] };
    }
  );

  server.tool("bart_get_fare", "Get Clipper and cash fare between two BART stations.",
    { origin: z.string(), destination: z.string() },
    async ({ origin, destination }) => {
      const o = resolveStation(origin), d = resolveStation(destination);
      const data = await bartGet("sched.aspx", { cmd: "fare", orig: o, dest: d }, apiKey);
      const fares: any[] = data?.root?.fares?.fare ?? [];
      const clipper = fares.find((f: any) => f.class === "clipper")?.amount ?? "N/A";
      const cash = fares.find((f: any) => f.class === "normal")?.amount ?? "N/A";
      return { content: [{ type: "text" as const, text: `BART Fare: ${o} → ${d}\n\n💳 Clipper: $${clipper}\n💵 Cash: $${cash}` }] };
    }
  );

  server.tool("bart_get_advisories", "Get current BART service advisories and delays.",
    { station: z.string().optional().default("") },
    async ({ station }) => {
      const params: Record<string, string> = { cmd: "bsa" };
      if (station) params["orig"] = resolveStation(station);
      const data = await bartGet("bsa.aspx", params, apiKey);
      const root = data?.root ?? {};
      let advisories: any[] = root.bsa ?? [];
      if (!Array.isArray(advisories)) advisories = advisories ? [advisories] : [];
      if (!advisories.length) return { content: [{ type: "text" as const, text: "✅ No advisories. Trains running normally." }] };
      const lines = advisories.map((a: any) => {
        const desc = a?.description?.["#cdata-section"] ?? a?.sms_text?.["#cdata-section"] ?? "No description";
        return `⚠️ ${a.type ?? "Alert"} (${a.station === "BART" ? "System-wide" : a.station ?? "Unknown"}): ${desc}`;
      });
      return { content: [{ type: "text" as const, text: `BART Advisories (${root.time ?? ""})\n\n${lines.join("\n\n")}` }] };
    }
  );

  server.tool("bart_get_elevator_status", "Get BART elevator outages for accessibility planning.", {},
    async () => {
      const data = await bartGet("bsa.aspx", { cmd: "elev" }, apiKey);
      const root = data?.root ?? {};
      let elevators: any[] = root.bsa ?? [];
      if (!Array.isArray(elevators)) elevators = elevators ? [elevators] : [];
      if (!elevators.length) return { content: [{ type: "text" as const, text: "✅ All elevators operating normally." }] };
      const lines = elevators.map((e: any) => `🛗 ${e.station ?? "Unknown"}: ${e?.description?.["#cdata-section"] ?? "No description"}`);
      return { content: [{ type: "text" as const, text: `Elevator Status (${root.time ?? ""})\n\n${lines.join("\n\n")}` }] };
    }
  );

  server.tool("bart_list_stations", "List all BART stations with names, abbreviations, and cities.", {},
    async () => {
      const data = await bartGet("stn.aspx", { cmd: "stns" }, apiKey);
      const stations: any[] = data?.root?.stations?.station ?? [];
      return { content: [{ type: "text" as const, text: `All BART Stations (${stations.length})\n\n${stations.map((s: any) => `${s.abbr} — ${s.name} (${s.city})`).join("\n")}` }] };
    }
  );

  return server;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const { pathname } = new URL(request.url);
    if (pathname === "/health") return new Response("OK", { status: 200 });
    if (pathname === "/mcp") {
      const handler = createMcpHandler(buildServer(env.BART_API_KEY));
      return handler(request, env, ctx);
    }
    return new Response("Not found", { status: 404 });
  },
};
