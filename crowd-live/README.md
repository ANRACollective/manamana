# Live station busyness — Mana-Mana crowd layer

Gives every station a real "how busy right now" score, because KL rail publishes
**no** official live crowding data.

## What I verified (2026-07-06, live)

- **No realtime rail feed exists.** data.gov.my's GTFS-Realtime API 404s for
  `rapid-rail-kl` — it only serves **buses**.
- **No occupancy anywhere.** I decoded a live bus vehicle: trip ID, route, GPS,
  vehicle ID, but **no `occupancy_status`**. Open data gives positions, never headcount.
- **Satellites are out.** No live coverage, can't see inside stations/trains.

So the crowd layer uses **Google Live Busyness** per station.

## How it plugs into the site

The Mana-Mana crowd layer now has three tiers, freshest wins:

1. **Community report** (Supabase) — a commuter's tap, overrides everything for 20 min.
2. **Live busyness** (this feed, `crowd.json`) — the baseline for every station.
3. **Time-of-day forecast** — fallback only where there's no busyness reading.

`mana-mana-v2-klang-valley.html` and `manamana-deploy/index.html` both fetch
`crowd.json` on load and every 5 min (`loadBusyness()`), map it by station name to
the glass fill, and label the source in the chip + station tooltip.

## Files

| File | Purpose |
|---|---|
| `stations.json` | 99 stations, auto-generated from the site's line data. |
| `collect_crowd.py` | Writes `crowd.json` (`{ busyness: { "Station": 0-100 } }`). |
| `crowd.json` | The feed. Copied to repo root + `manamana-deploy/` so the page can fetch it. |
| `index.html` | Standalone raw-feed QA view (not the product). |
| `../.github/workflows/refresh-crowd.yml` | Cron that regenerates + commits the feed. |

## Try it now (no keys)

```bash
cd crowd-live
python collect_crowd.py --sample     # realistic time-of-day fake data
```
Then open `mana-mana-v2-klang-valley.html` — stations now read from the feed and the
chip shows "Live station busyness". (Currently seeded with **sample** data.)

## Go live

The cron is set to the **free `populartimes` backend** by default so you can trial it
without a paid service:

1. Create a **Google Maps API key** (Google Cloud → enable *Geocoding API* + *Places API*).
   Google Cloud needs a card to create the key, but the free monthly credit easily
   covers this usage — you won't be charged at this volume.
2. In your GitHub repo: **Settings → Secrets and variables → Actions → New secret**
   → name `GMAPS_KEY`, paste your key.
3. `refresh-crowd.yml` runs on a ~5 min cron, regenerates `crowd.json`, and commits it
   to the repo root + `manamana-deploy/`. Deploy-from-branch serves it automatically.
   Trigger it once from the **Actions** tab to test.

`populartimes` scrapes Google, so it can break when Google changes its markup. When you
want something more robust, switch to **BestTime.app**: in the workflow, `pip install
requests`, change to `--backend besttime`, and set a `BESTTIME_KEY_PRIVATE` secret.

If the key is missing/expired the collector exits with an error and **won't** overwrite
a good `crowd.json`. The crowd board also shows an **"as of HH:MM"** stamp so stale data
is obvious at a glance.

## Accuracy caveat (already in the site footer)

Live busyness reflects people around the station, not turnstile counts. Directionally
right — packed vs quiet, rush vs off-peak — good enough for "should I leave now?", but
not official ridership.
