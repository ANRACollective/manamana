# Singapore feasibility — "Leave by" arrive-at planner

Prototype for a Mana-Mana Singapore feature: user tells us *"I need to be at
City Hall by 10:30 AM"* → we return **3 route options ranked by predicted
crowd**, not just fastest.

This folder mirrors `/crowd-live/` — a sandbox where the SG idea is proven
before folding into the main `index.html`.

## Why SG is worth the effort

KL rail publishes no realtime crowd feed, so `/crowd-live/` fakes it via
Google Live Busyness. SG publishes the exact signal officially: **LTA
DataMall's `PCDRealTime`** returns platform crowd per station per line,
refreshed every 10 min, plus **`PCDForecast`** with a 30-minute look-ahead.

Combined with **OneMap's Public Transport routing API**, we can do
something the incumbents don't: rank departure options by *predicted*
boarding-station crowd at *your* boarding time, not just current.

## Incumbent landscape (checked 2026-07-10)

| App | Crowd? | Notable |
|---|---|---|
| MyTransport.SG (official) | Yes, H/M/L link | 2.4/5 stars, chronic UI complaints — the beat-target |
| MRT In SG (indie, Caven) | Yes | Line-map centric, privacy-first |
| MRTCrowd.com | Yes | Single-purpose web |
| SG Bus+MRT | Bus load only | Crowd not the focus |
| Citymapper | No | Routing only |
| Google Maps | Popular times | Station-level, not platform-level, no forecast |

None of them combine **"leave by arrival time"** + **crowd-ranked
alternatives** + **community reports**. That's the gap.

## APIs verified

### OneMap Public Transport routing
- Endpoint: `https://www.onemap.gov.sg/api/public/routingsvc/route`
- `routeType=pt` unlocks `date`, `time`, `mode` (TRANSIT/BUS/RAIL),
  `maxWalkDistance`, `numItineraries`.
- **Auth:** Bearer token (can't safely be embedded in client) → **proxy required**.
- **Time semantics:** the docs describe `time` as departure. To do
  "arrive at 10:30", we sweep departure candidates backwards from the
  target and pick the latest that still arrives on time. This is what
  Google/Citymapper do internally.

### LTA DataMall
- Base: `http://datamall2.mytransport.sg/ltaodataservice`
- `PlatformCrowdDensityRealTime?TrainLine=NSL` — per-line, per-station,
  buckets `l | m | h`, updated every 10 min.
- `PCDForecast?TrainLine=NSL` — same shape, 30-min ahead.
- `TrainServiceAlerts` — disruptions, affected stations.
- **Auth:** `AccountKey: <key>` header → **proxy required** (no browser CORS).

## Proxy decision

Two paths that don't break the existing GitHub Pages deploy:

1. **Cloudflare Worker** at `manamana.io/api/*` — free tier, DNS route
   split. `/api/route` proxies OneMap, `/api/lta/*` proxies DataMall,
   both inject their secret headers server-side.
2. **Vercel edge function** on a subdomain (`sg.manamana.io`) — keeps
   Pages untouched, uses Vercel's free tier.

Prototype in this folder runs against **`sample-crowd.json` +
`sample-route.json`**, so you can demo the UX without any keys. Swap the
two `fetch()` calls in `index.html` to `/api/route` and `/api/lta/*`
when the proxy is live.

## Bucket → gradient mapping

LTA returns `l/m/h` per platform. The KL site uses a 0–100 gradient.
To keep the visual language, map:

```
l → 25   (Low, green)
m → 60   (Moderate, amber)
h → 90   (High, red)
```

The site labels show the discrete bucket ("Moderate") so the fake
precision doesn't leak.

## Ranking: least-crowded first

Per the scope decision, the picker returns the top 3 alternatives from
OneMap (`numItineraries=3`) and re-ranks them client-side by:

```
score(route) = max( crowdAtBoardingStationAtBoardingTime, for each MRT segment )
```

We look up **forecast** crowd at the boarding time (not current) —
that's the whole point of asking OneMap for a route that departs later.
Tie-broken by shortest travel time.

## Files

| File | Purpose |
|---|---|
| `stations.json` | 30-station prototype subset (major interchanges + branches). Full network is ~130 stations — extend when we go live. |
| `index.html` | Standalone "leave by" demo. Runs on sample data by default. |
| `sample-crowd.json` | Mock LTA `PCDForecast` response, shape-faithful. |
| `sample-route.json` | Mock OneMap `route?routeType=pt` response with 3 itineraries. |
| `collect_crowd.py` | *(follow-up)* Cron-style fetcher for `sg-crowd.json` — mirrors `/crowd-live/collect_crowd.py` for the station strip overlay. Not needed by the routing feature; add when we fold SG into the main site. |

## Try it now (no keys)

```
open sg-live/index.html
```

Type or pick a destination, set an arrive-by time, hit **Plan**. You get
three cards ranked by predicted crowd.

## Go live (later)

1. Deploy Cloudflare Worker at `manamana.io/api/route` and
   `manamana.io/api/lta/*` (script skeleton below).
2. Set Worker env vars: `ONEMAP_TOKEN`, `LTA_ACCOUNT_KEY`.
3. In `index.html`, swap the two sample fetches for the real endpoints.
4. Extend `stations.json` to the full ~130 stations (auto-gen from LTA
   `TrainStationCrowdDensity` metadata).

Worker sketch:

```js
export default {
  async fetch(req, env) {
    const url = new URL(req.url)
    if (url.pathname === '/api/route') {
      const params = url.searchParams
      const upstream = new URL('https://www.onemap.gov.sg/api/public/routingsvc/route')
      params.forEach((v, k) => upstream.searchParams.set(k, v))
      return fetch(upstream, { headers: { Authorization: `Bearer ${env.ONEMAP_TOKEN}` }})
    }
    if (url.pathname.startsWith('/api/lta/')) {
      const path = url.pathname.replace('/api/lta/', '')
      return fetch(`http://datamall2.mytransport.sg/ltaodataservice/${path}${url.search}`,
        { headers: { AccountKey: env.LTA_ACCOUNT_KEY, accept: 'application/json' }})
    }
    return new Response('not found', { status: 404 })
  }
}
```

## Not in scope for feasibility

- Full OneMap token-refresh flow (they expire; Worker cron handles that later).
- Community reports for SG — Supabase table + reuse KL's report UI.
- SG-specific parking (park-and-ride at Choa Chu Kang, Kranji, etc.) —
  KL's parking layer doesn't apply; separate work.
- Folding the SG code into `/index.html` behind a city toggle — do this
  after the standalone prototype validates the UX.
