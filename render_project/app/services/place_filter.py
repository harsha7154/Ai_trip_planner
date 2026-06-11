"""
Place filter service — production-level trip planning engine.

DAY PLANNING MODEL
==================
Three zones:  SRC (Day 1) | MID (inner days) | DST (last days)

  src_days  = 1           always
  dst_days  = 2 (5+day trips), 1 (3-4 day trips), 1 (2-day trip)
  mid_budget = days - src_days - dst_days

FLIGHT MODE
===========
When mode == "Flight":
  - Source city → nearest Odisha airport (haversine, shown in meta)
  - Trip planning starts FROM that airport city (entry district)
  - Total distance = flight distance (straight line, shown separately) +
    ground road distances within Odisha
  - Day 1 = journey day: fly source → nearest Odisha airport, then drive to first spot

MAX USEFUL DAYS per route:
  max_meaningful = 1 + (2 × len(mid_districts)) + 2
CATEGORY DIVERSITY:
  pick_3() picks 1 place per interest first, then fills unseen categories.
"""
from __future__ import annotations

import math
from typing import List, Dict, Any, Tuple, Optional

from loguru import logger

from app.data.loader import DataLoader
from app.geo.constants import INTEREST_CATS, DISTRICT_ADJACENT, CITY_COORDS
from app.geo.distance import (
    haversine_km,
    get_place_district,
    get_route_districts,
    city_coords,
    geo_route_sequence,
    geo_road_km,
    travel_time_str,
    is_odisha_city,
    nearest_odisha_entry_district,
    nearest_odisha_airport,
    ODISHA_DISTRICTS,
    ODISHA_AIRPORTS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Interest matching
# ─────────────────────────────────────────────────────────────────────────────

def matches_interest(category: str, interests: List[str]) -> bool:
    if not interests:
        return True
    cat = str(category).strip()
    for interest in interests:
        for kw in INTEREST_CATS.get(interest, [interest]):
            if kw.lower() == cat.lower():
                return True
            if len(kw) > 5 and kw.lower() in cat.lower():
                return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Pool building
# ─────────────────────────────────────────────────────────────────────────────

def pool_sorted(
    places: List[Dict[str, Any]],
    interests: List[str],
    key_fn,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    matched = sorted(
        [p for p in places if matches_interest(str(p.get("category", "")), interests)],
        key=key_fn,
    )
    others = sorted(
        [p for p in places if not matches_interest(str(p.get("category", "")), interests)],
        key=key_fn,
    )
    return matched, others


# ─────────────────────────────────────────────────────────────────────────────
# Place selection with cross-interest diversity
# ─────────────────────────────────────────────────────────────────────────────

def pick_3(
    matched: List[Dict],
    others: List[Dict],
    interests: Optional[List[str]] = None,
    exclude_names: Optional[set] = None,
) -> List[Dict]:
    excl = exclude_names or set()
    selected: List[Dict] = []
    sel_names: set = set()

    def _try_add(p: Dict) -> bool:
        pn = str(p.get("place_name", ""))
        if pn in sel_names or pn in excl:
            return False
        selected.append(p)
        sel_names.add(pn)
        return True

    if interests:
        for interest in interests:
            if len(selected) >= 3:
                break
            kws = INTEREST_CATS.get(interest, [interest])
            for p in matched:
                cat = str(p.get("category", ""))
                if any(kw.lower() == cat.lower() or (len(kw) > 5 and kw.lower() in cat.lower())
                       for kw in kws):
                    if _try_add(p):
                        break

    seen_cats = {str(p.get("category", "")) for p in selected}
    full_pool = matched + others
    for prefer_new in (True, False):
        for p in full_pool:
            if len(selected) >= 3:
                break
            cat = str(p.get("category", ""))
            if prefer_new and cat in seen_cats:
                continue
            if _try_add(p):
                seen_cats.add(cat)
        if len(selected) >= 3:
            break

    return selected[:3]


def pick_mid_spread(
    district_list: List[str],
    mid_by_dist: Dict[str, Tuple[List, List]],
    interests: List[str],
    exclude_names: Optional[set] = None,
) -> List[Dict]:
    excl = exclude_names or set()
    anchors: List[Dict] = []
    anchor_names: set = set()

    for d in district_list:
        dm, do_ = mid_by_dist.get(d, ([], []))
        for p in (dm + do_):
            pn = str(p.get("place_name", ""))
            if pn not in anchor_names and pn not in excl:
                anchors.append(p)
                anchor_names.add(pn)
                break

    fill_m = [p for d in district_list for p in mid_by_dist.get(d, ([], []))[0]
              if str(p.get("place_name", "")) not in anchor_names | excl]
    fill_o = [p for d in district_list for p in mid_by_dist.get(d, ([], []))[1]
              if str(p.get("place_name", "")) not in anchor_names | excl]

    return pick_3(anchors + fill_m, fill_o, interests,
                  exclude_names=anchor_names | excl)


# ─────────────────────────────────────────────────────────────────────────────
# Core day-slot builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_day_slots(
    days: int,
    mid_districts: List[str],
    src_m: List[Dict], src_o: List[Dict],
    dst_m: List[Dict], dst_o: List[Dict],
    mid_by_dist: Dict[str, Tuple[List, List]],
    src_district: str,
    dst_district: str,
    interests: List[str],
) -> Tuple[Dict[int, List[Dict]], Dict[int, str], Dict[int, str]]:

    db: Dict[int, List[Dict]] = {}
    dl: Dict[int, str] = {}
    dz: Dict[int, str] = {}
    used: set = set()

    def put(dn: int, places: List[Dict], label: str, zone: str) -> None:
        db[dn] = places
        dl[dn] = label
        dz[dn] = zone
        for p in places:
            used.add(str(p.get("place_name", "")))

    def src_pick(excl: set = None) -> List[Dict]:
        return pick_3(src_m, src_o, interests, exclude_names=excl or used)

    def dst_pick(excl: set = None) -> List[Dict]:
        return pick_3(dst_m, dst_o, interests, exclude_names=excl or used)

    def mid_pick(d: str, excl: set = None) -> List[Dict]:
        dm, do_ = mid_by_dist.get(d, ([], []))
        return pick_3(dm, do_, interests, exclude_names=excl or used)

    if days == 1:
        put(1, src_pick(set()), f"{src_district} Exploration", "src")
        return db, dl, dz

    if days == 2:
        put(1, src_pick(set()), f"{src_district} Exploration", "src")
        put(2, dst_pick(), f"{dst_district} Exploration", "dst")
        return db, dl, dz

    if days == 3:
        put(1, src_pick(set()), f"{src_district} Exploration", "src")
        if mid_districts:
            put(2, pick_mid_spread(mid_districts, mid_by_dist, interests, used),
                " → ".join(mid_districts) + " Route", "mid")
        else:
            put(2, src_pick(), f"{src_district} Extended", "src")
        put(3, dst_pick(), f"{dst_district} Exploration", "dst")
        return db, dl, dz

    if days == 4:
        put(1, src_pick(set()), f"{src_district} Exploration", "src")
        if not mid_districts:
            put(2, src_pick(), f"{src_district} Extended", "src")
            put(3, dst_pick(), f"{dst_district} Exploration", "dst")
            put(4, dst_pick(), f"{dst_district} Extended", "dst")
        elif len(mid_districts) == 1:
            put(2, mid_pick(mid_districts[0]), f"{mid_districts[0]} Route", "mid")
            put(3, dst_pick(), f"{dst_district} Exploration", "dst")
            put(4, dst_pick(), f"{dst_district} Extended", "dst")
        else:
            half = max(1, len(mid_districts) // 2)
            first, second = mid_districts[:half], mid_districts[half:]
            put(2, pick_mid_spread(first, mid_by_dist, interests, used),
                " → ".join(first) + " Route", "mid")
            put(3, pick_mid_spread(second, mid_by_dist, interests, used),
                " → ".join(second) + " Route", "mid")
            put(4, dst_pick(), f"{dst_district} Exploration", "dst")
        return db, dl, dz

    # 5+ days
    n_mids = len(mid_districts)
    dst_days = 2
    mid_budget = days - 1 - dst_days

    put(1, src_pick(set()), f"{src_district} Exploration", "src")
    put(days - 1, dst_pick(), f"{dst_district} Exploration", "dst")
    put(days,     dst_pick(), f"{dst_district} Extended", "dst")

    mid_day_nums = list(range(2, days - 1))

    if n_mids == 0:
        for idx, dn in enumerate(mid_day_nums):
            if idx % 2 == 0:
                picks = pick_3([p for p in src_m+src_o if str(p.get("place_name","")) not in used],
                               [], interests, used)
                zone, label = "src", f"{src_district} Depth"
            else:
                picks = pick_3([p for p in dst_m+dst_o if str(p.get("place_name","")) not in used],
                               [], interests, used)
                zone, label = "dst", f"{dst_district} Depth"
            if not picks:
                picks = src_pick(set()) if idx % 2 == 0 else dst_pick(set())
            put(dn, picks, label, zone)

    elif mid_budget <= n_mids:
        chunks: List[List[str]] = [[] for _ in range(mid_budget)]
        for i, d in enumerate(mid_districts):
            chunks[i % mid_budget].append(d)
        for dn, chunk in zip(mid_day_nums, chunks):
            if len(chunk) == 1:
                put(dn, mid_pick(chunk[0]), f"{chunk[0]} Route", "mid")
            else:
                put(dn, pick_mid_spread(chunk, mid_by_dist, interests, used),
                    " → ".join(chunk) + " Route", "mid")

    else:
        primary = mid_day_nums[:n_mids]
        overflow = mid_day_nums[n_mids:]

        for dn, d in zip(primary, mid_districts):
            put(dn, mid_pick(d), f"{d} Route", "mid")

        for idx, dn in enumerate(overflow):
            cycle_d = mid_districts[idx % n_mids]
            picks = mid_pick(cycle_d)
            if picks:
                put(dn, picks, f"{cycle_d} Extended", "mid")
            else:
                if idx % 2 == 0:
                    picks = pick_3([p for p in src_m+src_o if str(p.get("place_name","")) not in used],
                                   [], interests, used) or src_pick(set())
                    put(dn, picks, f"{src_district} Extended", "src")
                else:
                    picks = pick_3([p for p in dst_m+dst_o if str(p.get("place_name","")) not in used],
                                   [], interests, used) or dst_pick(set())
                    put(dn, picks, f"{dst_district} Extended", "dst")

    return db, dl, dz


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

async def get_trip_places(
    source: str,
    destination: str,
    interests: List[str],
    mode: str,
    days: int,
    loader: DataLoader,
) -> Tuple[str, Dict[str, List[str]]]:

    places = loader.places
    is_flight = mode.lower() == "flight"

    # Coords for source and destination
    src_coords = city_coords(source, loader) or (20.2961, 85.8245)
    dst_coords = city_coords(destination, loader) or (19.8043, 85.8174)
    src_lat, src_lon = src_coords
    dst_lat, dst_lon = dst_coords

    source_is_external = not is_odisha_city(source, loader)
    external_src_label = source

    # ── Flight mode: find nearest Odisha airport to source ───────────────────
    flight_airport: Optional[Dict] = None
    flight_air_km: float = 0.0
    airport_to_entry_km: float = 0.0
    airport_to_entry_mins: int = 0

    if is_flight and source_is_external:
        flight_airport = nearest_odisha_airport(src_lat, src_lon)
        flight_air_km = round(haversine_km(src_lat, src_lon, flight_airport["lat"], flight_airport["lon"]), 1)
        # Road from airport to destination district
        air_to_dst = await geo_road_km(
            flight_airport["lat"], flight_airport["lon"], dst_lat, dst_lon, "Road"
        )
        airport_to_entry_km = air_to_dst["km"]
        airport_to_entry_mins = air_to_dst["mins"]
        # Use airport city as effective entry point for Odisha planning
        entry_district = flight_airport["district"]
        entry_lat = flight_airport["lat"]
        entry_lon = flight_airport["lon"]
        effective_src_district = entry_district
        effective_src_lat, effective_src_lon = entry_lat, entry_lon
        logger.info(
            f"[Flight] {source} → {flight_airport['iata']} ({flight_airport['city']}) "
            f"~{flight_air_km} km as the crow flies → then road to {destination}"
        )
    elif source_is_external:
        entry_district, entry_lat, entry_lon = nearest_odisha_entry_district(src_lat, src_lon)
        effective_src_district = entry_district
        effective_src_lat, effective_src_lon = entry_lat, entry_lon
        logger.info(f"External source '{source}' → nearest Odisha entry: {entry_district}")
    else:
        effective_src_district = get_place_district(source, loader)
        effective_src_lat, effective_src_lon = src_lat, src_lon

    src_district = effective_src_district
    dst_district = get_place_district(destination, loader)
    mid_districts = get_route_districts(src_district, dst_district)

    src_allowed = set([src_district] + DISTRICT_ADJACENT.get(src_district, []))
    dst_allowed = set([dst_district] + DISTRICT_ADJACENT.get(dst_district, []))
    mid_allowed = set(mid_districts)

    logger.info(f"Route: {src_district} → {' → '.join(mid_districts) or '(direct)'} → {dst_district}")

    eff_src_lat = effective_src_lat if source_is_external else src_lat
    eff_src_lon = effective_src_lon if source_is_external else src_lon

    # Enrich places with haversine distances (for filtering/sorting only)
    enriched: List[Dict[str, Any]] = []
    image_map: Dict[str, List[str]] = {}

    for p in places:
        try:
            plat, plon = float(p["latitude"]), float(p["longitude"])
        except Exception:
            continue
        p_dist = str(p.get("district", "")).strip()
        imgs = loader.parse_image_urls(p.get("image_urls", ""))
        if imgs:
            image_map[str(p.get("place_name", ""))] = imgs
        enriched.append({
            **p,
            "d_src":      haversine_km(eff_src_lat, eff_src_lon, plat, plon),
            "d_dst":      haversine_km(dst_lat, dst_lon, plat, plon),
            "in_src":     p_dist in src_allowed,
            "in_dst":     p_dist in dst_allowed,
            "in_mid":     p_dist in mid_allowed,
            "p_district": p_dist,
        })

    # Pools sorted by haversine (used only for shortlisting)
    src_m, src_o = pool_sorted(
        [p for p in enriched if p["in_src"]], interests, lambda x: x["d_src"]
    )
    dst_m, dst_o = pool_sorted(
        [p for p in enriched if p["in_dst"]], interests, lambda x: x["d_dst"]
    )

    mid_by_dist: Dict[str, Tuple[List, List]] = {}
    prev_lat, prev_lon = eff_src_lat, eff_src_lon
    for d in mid_districts:
        pool = [p for p in enriched if p["in_mid"] and p["p_district"] == d]
        _lt, _ln = prev_lat, prev_lon
        mid_by_dist[d] = pool_sorted(
            pool, interests,
            lambda x, lt=_lt, ln=_ln: haversine_km(lt, ln, float(x["latitude"]), float(x["longitude"])),
        )
        prev_lat, prev_lon = CITY_COORDS.get(d.lower(), (prev_lat, prev_lon))

    # ── Total road distance (REAL road distance within Odisha only) ───────────
    # Build waypoints WITHIN Odisha (airport/entry → mid districts → destination)
    odisha_waypoints = [(eff_src_lat, eff_src_lon)]
    for d in mid_districts:
        dc = CITY_COORDS.get(d.lower())
        if dc:
            odisha_waypoints.append(dc)
    odisha_waypoints.append((dst_lat, dst_lon))

    # Get REAL road distances for Odisha leg
    total_road_km_odisha = 0.0
    for i in range(len(odisha_waypoints) - 1):
        a, b = odisha_waypoints[i], odisha_waypoints[i + 1]
        seg = await geo_road_km(a[0], a[1], b[0], b[1], "Road")
        total_road_km_odisha += seg["km"]
    total_road_km_odisha = round(total_road_km_odisha, 1)

    # For flight: total = flight km (air) + Odisha road km
    # For road/train from external: total = haversine source→entry × 1.3 + Odisha road
    if is_flight and source_is_external and flight_airport:
        total_km = round(flight_air_km + airport_to_entry_km, 1)
        # For display the LLM gets both numbers
    elif source_is_external:
        src_to_entry_hav = haversine_km(src_lat, src_lon, eff_src_lat, eff_src_lon)
        src_to_entry_road = round(src_to_entry_hav * 1.3, 1)
        total_km = round(src_to_entry_road + total_road_km_odisha, 1)
    else:
        total_km = total_road_km_odisha

    realistic_days = max(1, math.ceil(total_km / 200))
    max_meaningful_days = 1 + (2 * len(mid_districts)) + 2

    # Build day slots
    day_buckets, day_labels, day_zones = _build_day_slots(
        days, mid_districts,
        src_m, src_o, dst_m, dst_o,
        mid_by_dist, src_district, dst_district, interests,
    )

    # Geo ordering with REAL road distances between stops
    for dn in sorted(day_buckets.keys()):
        pl   = day_buckets[dn]
        zone = day_zones.get(dn, "dst")
        rlat = eff_src_lat if zone in ("src", "mid") else dst_lat
        rlon = eff_src_lon if zone in ("src", "mid") else dst_lon
        if pl:
            day_buckets[dn] = await geo_route_sequence(pl, rlat, rlon, dst_lat, dst_lon, mode)

    # Suggestions
    assigned = {str(p.get("place_name","")) for pl in day_buckets.values() for p in pl}
    sugg_src = [p for p in src_m + src_o if str(p.get("place_name","")) not in assigned][:5]
    sugg_dst = [p for p in dst_m + dst_o if str(p.get("place_name","")) not in assigned][:5]
    mid_sugg: Dict[str, List[Dict]] = {}
    for d in mid_districts:
        m, o = mid_by_dist.get(d, ([], []))
        s = [p for p in m + o if str(p.get("place_name","")) not in assigned][:5]
        if s:
            mid_sugg[d] = s

    # Route strings
    district_route_str = " → ".join([src_district] + mid_districts + [dst_district])
    if source_is_external:
        if is_flight and flight_airport:
            route_string = (
                f"{source} ✈ {flight_airport['iata']} ({flight_airport['city']}) → "
                f"{'→'.join(mid_districts)+' →' if mid_districts else ''} {destination}"
            )
            district_route_str = f"{source} ✈ {flight_airport['city']} → {district_route_str}"
        else:
            route_string = f"{source} → {src_district} → {'→'.join(mid_districts)+' →' if mid_districts else ''} {destination}"
            district_route_str = f"{source} → {district_route_str}"
    else:
        route_string = f"{source} → {'→'.join(mid_districts)+' →' if mid_districts else ''} {destination}"

    # ── LLM context string ────────────────────────────────────────────────────
    lines = [
        f"TRIP_META: {source} → {destination} | {days} days | {mode}",
        f"REALISTIC_DAYS_POSSIBLE: {realistic_days}",
        f"MAX_MEANINGFUL_DAYS: {max_meaningful_days}",
        f"DIST_LABEL: source={src_district} | dest={dst_district} | mid={'|'.join(mid_districts)}" + (f" | external_src={source}" if source_is_external else ""),
        f"ROUTE_STRING: {route_string}",
        f"DISTRICT_ROUTE: {district_route_str}",
        f"TOTAL_ROUTE_KM: {round(total_km, 1)}",
        f"ODISHA_ROAD_KM: {total_road_km_odisha}",
        f"EXTERNAL_SOURCE: {source if source_is_external else ''}",
        f"IS_FLIGHT: {'yes' if is_flight else 'no'}",
    ]

    if is_flight and flight_airport:
        lines += [
            f"FLIGHT_INFO: {source} → {flight_airport['iata']} | Airport: {flight_airport['name']} | City: {flight_airport['city']} | Air distance: {flight_air_km} km",
            f"AIRPORT_TO_DEST_ROAD: {airport_to_entry_km} km, {travel_time_str(airport_to_entry_mins)} by road",
        ]
    lines.append("")

    def place_block(p: Dict, tag: str, ref_name: str, zone_hint: str) -> str:
        pname  = str(p.get("place_name", ""))
        cat    = str(p.get("category", ""))
        pd_    = str(p.get("p_district", ""))
        dkm    = p.get("distance_from_prev",
                       p.get("d_src" if zone_hint in ("src","mid") else "d_dst", 0))
        tm     = p.get("time_from_prev", 0)
        return (
            f"  [{tag}] {pname} | {cat} | {pd_}\n"
            f"  DIST: {dkm} km, {travel_time_str(tm) if tm else 'N/A'} from {ref_name}\n"
            f"  Speciality: {str(p.get('importance','')).strip()[:200]}\n"
            f"  Best month: {str(p.get('best_time','')).strip()}\n"
            f"  Must-Try food: {str(p.get('food_speciality','')).strip()}\n"
            f"  Entry fee: {str(p.get('entry_ticket','')).strip()}\n"
            f"  Activities: {str(p.get('activities_budget','')).strip()[:200]}\n"
            f"  OTDC Stay: {str(p.get('otdc_stay','')).strip()}\n"
            f"  Map: {str(p.get('map_link','')).strip()}\n"
            f"  IMAGES: {','.join(image_map.get(pname,[]))}\n"
        )

    for dn in sorted(day_buckets.keys()):
        pl    = day_buckets[dn]
        label = day_labels.get(dn, f"Day {dn}")
        zone  = day_zones.get(dn, "dst")
        ref   = source if zone in ("src","mid") else destination
        lines.append(f"--- DAY {dn} — {label} ({len(pl)} places) ---")
        for p in pl:
            lines.append(place_block(p, f"DAY{dn}", ref, zone))

    empty = [dn for dn in sorted(day_buckets) if not day_buckets[dn]]
    if empty:
        lines += ["", f"COVERAGE_NOTE: No verified places for day(s): {empty}.",
                  "Write local leisure day for those days."]

    lines += ["", "SUGGESTION_ZONES:"]
    if sugg_src:
        lines.append(f"ZONE|{src_district} Route Suggestions")
        for p in sugg_src:
            lines.append(f"  SPLACE|{p.get('place_name','')}|{p.get('category','')}|"
                         f"{p.get('p_district','')}|{str(p.get('map_link','')).strip()}")
    for d_name, slist in mid_sugg.items():
        lines.append(f"ZONE|{d_name} Route Suggestions")
        for p in slist:
            lines.append(f"  SPLACE|{p.get('place_name','')}|{p.get('category','')}|"
                         f"{p.get('p_district','')}|{str(p.get('map_link','')).strip()}")
    if sugg_dst:
        lines.append(f"ZONE|{dst_district} Route Suggestions")
        for p in sugg_dst:
            lines.append(f"  SPLACE|{p.get('place_name','')}|{p.get('category','')}|"
                         f"{p.get('p_district','')}|{str(p.get('map_link','')).strip()}")

    # Nature camps
    all_zone = src_allowed | mid_allowed | dst_allowed
    nature_camps = sorted(
        [p for p in enriched
         if str(p.get("category","")).strip() == "Nature Camps"
         and p.get("p_district","") in all_zone],
        key=lambda x: x["d_src"],
    )
    if nature_camps:
        lines += ["", "NATURE_CAMPS:"]
        for nc in nature_camps[:5]:
            n = nc.get("place_name","")
            lines.append(
                f"  NC|{n}|{nc.get('p_district','')}|"
                f"{str(nc.get('importance','')).strip()[:150]}|"
                f"{str(nc.get('entry_ticket','')).strip()}|"
                f"{str(nc.get('activities_budget','')).strip()[:150]}|"
                f"{str(nc.get('food_speciality','')).strip()}|"
                f"{str(nc.get('best_time','')).strip()}|"
                f"{str(nc.get('map_link','')).strip()}|"
                f"{','.join(image_map.get(n,[]))}|"
                f"{str(nc.get('otdc_stay','')).strip()}"
            )

    return "\n".join(lines), image_map
