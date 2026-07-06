#!/usr/bin/env python3
"""
KL rail live-crowd collector  ->  crowd.json

There is NO official live crowding feed for KL trains (data.gov.my only serves
GTFS-Realtime for buses, and even that has no occupancy field). So we approximate
"how busy is this station right now" with Google's Live Busyness signal.

Output feeds the Mana-Mana V2 site as its BASELINE crowd layer. On the site,
priority is:  fresh community report  >  this live-busyness feed  >  time-of-day fallback.

Run:
    python collect_crowd.py --sample                 # realistic fake data, no keys
    python collect_crowd.py --backend besttime       # BestTime.app (recommended)
    python collect_crowd.py --backend populartimes   # free Google scraper lib

crowd.json shape:
    { "updated": ISO8601, "backend": "...", "busyness": { "KL Sentral": 82, ... } }
    scores are 0-100. Stations with no reading are omitted (site falls back).

Backends
--------
BestTime.app (recommended):  pip install requests ; export BESTTIME_KEY_PRIVATE=pri_xxx
populartimes (free/fragile):  pip install git+https://github.com/m-wrzr/populartimes
                              export GMAPS_KEY=AIza...   (Google Maps Places key)
"""
import argparse, json, os, random, sys, datetime, pathlib

HERE = pathlib.Path(__file__).parent
STATIONS = json.loads((HERE / "stations.json").read_text(encoding="utf-8"))["stations"]

def now_iso():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

# ---------------------------------------------------------------- sample
_HUBS = {"KL Sentral","Masjid Jamek","KLCC","Bukit Bintang","Titiwangsa","Hang Tuah",
         "Chan Sow Lin","Putra Heights","Ampang Park","Pasar Seni","Bandar Tasik Selatan"}
def backend_sample(st):
    """Realistic fake score from time-of-day + hub weighting, for demoing the UI."""
    h = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).hour
    peak = max(0, 100 - min(abs(h - 8), abs(h - 18)) * 22)   # rush ~8am / ~6pm
    return max(0, min(100, peak + (18 if st["name"] in _HUBS else 0) + random.randint(-15, 15)))

# ---------------------------------------------------------------- BestTime
def backend_besttime(st):
    import requests
    r = requests.get("https://besttime.app/api/v1/forecasts/live", params={
        "api_key_private": os.environ["BESTTIME_KEY_PRIVATE"],
        "venue_name": st["name"],
        "venue_address": st["query"],
    }, timeout=30)
    r.raise_for_status()
    return r.json().get("analysis", {}).get("venue_live_busyness")

# ---------------------------------------------------------------- populartimes
def backend_populartimes(st):
    import populartimes, requests
    # geocode the station, then read live busyness for the matched place
    key = os.environ["GMAPS_KEY"]
    g = requests.get("https://maps.googleapis.com/maps/api/geocode/json",
                     params={"address": st["query"], "key": key}, timeout=30).json()
    loc = g["results"][0]["geometry"]["location"]
    res = populartimes.get(key, ["train_station", "subway_station"],
                           (loc["lat"] - 0.0015, loc["lng"] - 0.0015),
                           (loc["lat"] + 0.0015, loc["lng"] + 0.0015))
    for place in res:
        if "current_popularity" in place:
            return place["current_popularity"]
    return None

BACKENDS = {"sample": backend_sample, "besttime": backend_besttime, "populartimes": backend_populartimes}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="sample", choices=BACKENDS.keys())
    ap.add_argument("--sample", action="store_true", help="alias for --backend sample")
    args = ap.parse_args()
    backend = "sample" if args.sample else args.backend
    fn = BACKENDS[backend]

    busyness = {}
    for st in STATIONS:
        try:
            score = fn(st)
        except Exception as e:
            print(f"  ! {st['name']}: {e}", file=sys.stderr); score = None
        if score is not None:
            busyness[st["name"]] = int(round(score))

    # safeguard: never write an empty feed from a real backend (e.g. missing/expired key),
    # which would blow away a previously-good crowd.json. Fail loudly instead.
    if backend != "sample" and not busyness:
        sys.exit(f"ERROR: {backend} returned 0 stations — leaving crowd.json untouched. Check your API key.")

    out = {"updated": now_iso(), "backend": backend, "busyness": busyness}
    (HERE / "crowd.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote crowd.json — {backend} backend, {len(busyness)}/{len(STATIONS)} stations at {out['updated']}")

if __name__ == "__main__":
    main()
