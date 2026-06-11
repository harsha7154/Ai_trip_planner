"""
Geography constants for Odisha trip planning.
- CITY_COORDS      : lat/lon for all major cities and tourist spots
- DISTRICT_ADJACENT: district adjacency graph for BFS route planning
- INTEREST_CATS    : interest keyword → Excel category mapping

PRODUCTION FIX NOTES:
  - Removed duplicate alias districts (Baleswar, Bolangir, Sundergarh, Phulbani,
    Bhawanipatna, Sonepur) that had no places in Excel data but polluted BFS.
  - Trimmed false adjacencies >130km apart that caused BFS to skip real intermediates.
  - Added Khordha↔Jajpur, Cuttack↔Angul, Cuttack↔Keonjhar links that were missing,
    causing Bhubaneswar→Balasore / Cuttack→Rourkela to come back as "direct" (0 mids).
"""
from typing import Dict, Tuple, List

# ── Interest → Category keyword mapping ──────────────────────────────────────
INTEREST_CATS: Dict[str, List[str]] = {
    "Temples":      ["Temple", "Religious", "Mandir", "Dham", "Shrine", "Temples"],
    "Beaches":      ["Beach", "Coastal", "Sea", "Beaches"],
    "Heritage":     ["Heritage Sites", "Monument", "Fort", "Cave", "UNESCO", "Historical", "Palace", "Heritage"],
    "Nature":       ["Nature", "Park", "Wildlife", "Forest", "Lake", "Dam", "Waterfall", "Garden"],
    "Trekking":     ["Trek", "Hill", "Mountains", "Peak", "Valley", "Mountain"],
    "Adventure":    ["Adventure", "Safari", "Sports", "Rafting", "Camping", "Wildlife"],
    "Food":         ["Food", "Market", "Cuisine", "Street Food"],
    "Eco-Tourism":  ["Eco-Tourism", "Eco Tourism", "Ecotourism", "Forest", "Wildlife", "Sanctuary", "Reserve", "Eco"],
    "Culture":      ["Culture", "Cultural", "Festival", "Tribal", "Art", "Craft", "Tradition", "Dance"],
    "Wildlife":     ["Wildlife", "Sanctuary", "Tiger", "Reserve", "National Park", "Safari", "Elephant"],
    "Nature Camps": ["Nature Camps", "Nature Camp", "Eco Camp", "Forest Camp", "Camp"],
}

# ── City / Tourist-spot coordinates ──────────────────────────────────────────
CITY_COORDS: Dict[str, Tuple[float, float]] = {
    # District Headquarters
    "angul":           (20.8400, 85.1010),
    "balangir":        (20.7167, 83.4833),
    "bolangir":        (20.7167, 83.4833),
    "balasore":        (21.4940, 86.9335),
    "baleswar":        (21.4940, 86.9335),
    "bargarh":         (21.3333, 83.6167),
    "bhadrak":         (21.0544, 86.4998),
    "boudh":           (20.8361, 84.3244),
    "cuttack":         (20.4625, 85.8830),
    "deogarh":         (21.5333, 84.7333),
    "dhenkanal":       (20.6628, 85.5988),
    "gajapati":        (19.3167, 84.1000),
    "paralakhemundi":  (18.7800, 84.0900),
    "chatrapur":       (19.3560, 84.9900),
    "jagatsinghpur":   (20.2583, 86.1683),
    "jajpur":          (20.8497, 86.3350),
    "jharsuguda":      (21.8553, 84.0063),
    "kalahandi":       (19.9133, 83.1722),
    "bhawanipatna":    (19.9133, 83.1722),
    "kandhamal":       (20.1167, 84.2333),
    "phulbani":        (20.4800, 84.2300),
    "kendrapara":      (20.4971, 86.4228),
    "kendujhar":       (21.6285, 85.5815),
    "keonjhar":        (21.6285, 85.5815),
    "khordha":         (20.1826, 85.6159),
    "malkangiri":      (18.3500, 81.8833),
    "mayurbhanj":      (21.9333, 86.7333),
    "nabarangpur":     (19.2333, 82.5500),
    "nayagarh":        (20.1289, 85.0958),
    "nuapada":         (20.8000, 82.5333),
    "rayagada":        (19.1667, 83.4167),
    "sonepur":         (20.8333, 83.9167),
    "subarnapur":      (20.8333, 83.9167),
    "sundargarh":      (22.1167, 84.0333),
    "sundergarh":      (22.1167, 84.0333),
    # Major Cities
    "bhubaneswar":     (20.2961, 85.8245),
    "puri":            (19.8043, 85.8174),
    "konark":          (19.8876, 86.0945),
    "berhampur":       (19.3150, 84.7941),
    "brahmapur":       (19.3150, 84.7941),
    "sambalpur":       (21.4669, 83.9812),
    "baripada":        (21.9333, 86.7333),
    "koraput":         (18.8135, 82.7120),
    "rourkela":        (22.2604, 84.8536),
    "jeypore":         (18.8500, 82.5667),
    # Tourist Spots
    "chilika":         (19.7248, 85.3200),
    "satapada":        (19.6683, 85.5350),
    "rambha":          (19.5000, 85.1000),
    "gopalpur":        (19.2575, 84.9069),
    "chandrabhaga":    (19.8870, 86.0790),
    "daringbadi":      (19.9167, 84.1333),
    "deomali":         (18.7500, 82.9333),
    "tikarpada":       (20.8667, 84.7500),
    "satkosia":        (20.7167, 84.5333),
    "bhitarkanika":    (20.7500, 86.8833),
    "simlipal":        (21.8333, 86.2500),
    "balighai":        (19.8600, 85.9300),
    "raghurajpur":     (19.9200, 85.8700),
    "pipili":          (20.0333, 85.6667),
    "dhauli":          (20.2167, 85.8500),
    "udayagiri":       (20.1289, 85.0958),
    "ratnagiri":       (20.5500, 86.5333),
    "lalitgiri":       (20.5333, 86.4000),
    "nandankanan":     (20.3833, 85.7667),
    "khandagiri":      (20.2667, 85.7667),
    "taptapani":       (19.6667, 84.3667),
    "hirakud":         (21.5167, 83.8667),
    "debrigarh":       (21.6000, 83.7167),
    "huma":            (21.3000, 83.8500),
    "gupteswar":       (18.6833, 82.4167),
    "duduma":          (18.6167, 82.8667),
    "paradip":         (20.3167, 86.6167),
    "talasari":        (21.5833, 87.1833),
    "chandipur":       (21.4500, 87.0500),
    "panchalingeswar": (21.7167, 86.5833),
    "joranda":         (20.6500, 84.8333),
    "barehipani":      (22.1000, 86.2167),
    "kapilash":        (20.8167, 85.6500),
    "bonai":           (22.0000, 84.9333),
    # ── Major Indian Cities (non-Odisha) — for external source routing ───────
    "hyderabad":       (17.3850, 78.4867),
    "secunderabad":    (17.4399, 78.4983),
    "mumbai":          (19.0760, 72.8777),
    "pune":            (18.5204, 73.8567),
    "bangalore":       (12.9716, 77.5946),
    "bengaluru":       (12.9716, 77.5946),
    "chennai":         (13.0827, 80.2707),
    "delhi":           (28.6139, 77.2090),
    "new delhi":       (28.6139, 77.2090),
    "kolkata":         (22.5726, 88.3639),
    "calcutta":        (22.5726, 88.3639),
    "ahmedabad":       (23.0225, 72.5714),
    "nagpur":          (21.1458, 79.0882),
    "visakhapatnam":   (17.6868, 83.2185),
    "vizag":           (17.6868, 83.2185),
    "vijayawada":      (16.5062, 80.6480),
    "patna":           (25.5941, 85.1376),
    "ranchi":          (23.3441, 85.3096),
    "raipur":          (21.2514, 81.6296),
    "dhanbad":         (23.7957, 86.4304),
    "jamshedpur":      (22.8046, 86.2029),
    "bokaro":          (23.6693, 86.1511),
    # North India
    "lucknow":         (26.8467, 80.9462),
    "kanpur":          (26.4499, 80.3319),
    "varanasi":        (25.3176, 82.9739),
    "allahabad":       (25.4358, 81.8463),
    "prayagraj":       (25.4358, 81.8463),
    "agra":            (27.1767, 78.0081),
    "jaipur":          (26.9124, 75.7873),
    "chandigarh":      (30.7333, 76.7794),
    "amritsar":        (31.6340, 74.8723),
    "ludhiana":        (30.9010, 75.8573),
    "jalandhar":       (31.3260, 75.5762),
    "punjab":          (31.1471, 75.3412),   # Geographic centre of Punjab state
    "patiala":         (30.3398, 76.3869),
    "mohali":          (30.7046, 76.7179),
    "bathinda":        (30.2110, 74.9455),
    "pathankot":       (32.2643, 75.6520),
    "shimla":          (31.1048, 77.1734),
    "dehradun":        (30.3165, 78.0322),
    "haridwar":        (29.9457, 78.1642),
    "jodhpur":         (26.2389, 73.0243),
    "udaipur":         (24.5854, 73.7125),
    "surat":           (21.1702, 72.8311),
    "indore":          (22.7196, 75.8577),
    "bhopal":          (23.2599, 77.4126),
    "guwahati":        (26.1445, 91.7362),
    "imphal":          (24.8170, 93.9368),
    "coimbatore":      (11.0168, 76.9558),
    "kochi":           (9.9312, 76.2673),
    "thiruvananthapuram": (8.5241, 76.9366),
    "madurai":         (9.9252, 78.1198),
}

# ── District Adjacency Map ────────────────────────────────────────────────────
# PRODUCTION RULES:
#   1. Only districts that exist in places.xlsx as canonical names.
#   2. Only include an edge if the two district HQs are within ~130km of each other
#      (beyond that, BFS will correctly insert the real intermediate districts).
#   3. No alias keys (Baleswar, Bolangir, Sundergarh, Phulbani, Bhawanipatna,
#      Sonepur) — they have no Excel data and pollute BFS shortest-path.
#
# KEY FIXES vs original:
#   + Khordha ↔ Jajpur   (missing — caused Bhubaneswar→Balasore to return "direct")
#   + Cuttack ↔ Angul    (missing — caused Cuttack→Rourkela to return "direct")
#   + Cuttack ↔ Keonjhar (missing — alternate northern path)
#   + Khordha ↔ Angul    via Dhenkanal corridor
#   - Removed Nabarangpur↔Bolangir (191km — too far, skipped Nuapada/Kalahandi)
#   - Removed Keonjhar↔Sundargarh (169km — skipped Deogarh/Angul)
#   - Removed Sambalpur↔Angul     (135km — skipped Deogarh)
#   - Removed Kalahandi↔Bargarh   (164km — skipped Nuapada)

DISTRICT_ADJACENT: Dict[str, List[str]] = {
    # ── Coastal / East ────────────────────────────────────────────────────────
    "Puri":          ["Khordha", "Nayagarh", "Ganjam", "Jagatsinghpur"],
    "Khordha":       ["Puri", "Nayagarh", "Cuttack", "Jagatsinghpur", "Jajpur"],
    "Jagatsinghpur": ["Cuttack", "Kendrapara", "Puri", "Khordha"],
    "Kendrapara":    ["Cuttack", "Jagatsinghpur", "Bhadrak", "Jajpur"],
    "Jajpur":        ["Cuttack", "Kendrapara", "Bhadrak", "Keonjhar", "Dhenkanal", "Khordha"],
    "Bhadrak":       ["Balasore", "Jajpur", "Kendrapara"],
    "Balasore":      ["Bhadrak", "Mayurbhanj", "Jajpur"],
    "Mayurbhanj":    ["Balasore", "Keonjhar", "Bhadrak"],

    # ── Central / North ───────────────────────────────────────────────────────
    "Cuttack":       ["Khordha", "Jagatsinghpur", "Kendrapara", "Jajpur",
                      "Dhenkanal", "Nayagarh", "Angul", "Keonjhar"],
    "Dhenkanal":     ["Cuttack", "Angul", "Keonjhar", "Jajpur"],
    "Angul":         ["Dhenkanal", "Deogarh", "Boudh", "Keonjhar", "Cuttack"],
    "Keonjhar":      ["Mayurbhanj", "Deogarh", "Angul", "Jajpur", "Dhenkanal", "Cuttack"],
    "Deogarh":       ["Sambalpur", "Angul", "Keonjhar", "Sundargarh"],
    "Sundargarh":    ["Deogarh", "Jharsuguda", "Sambalpur"],

    # ── West ──────────────────────────────────────────────────────────────────
    "Sambalpur":     ["Bargarh", "Jharsuguda", "Deogarh", "Boudh", "Subarnapur"],
    "Jharsuguda":    ["Sambalpur", "Sundargarh", "Bargarh"],
    "Bargarh":       ["Sambalpur", "Balangir", "Nuapada", "Jharsuguda"],
    "Subarnapur":    ["Sambalpur", "Bargarh", "Balangir", "Boudh"],
    "Boudh":         ["Sambalpur", "Balangir", "Kandhamal", "Nayagarh", "Angul", "Subarnapur"],
    "Balangir":      ["Bargarh", "Subarnapur", "Nuapada", "Kalahandi", "Boudh", "Kandhamal"],

    # ── South-West ────────────────────────────────────────────────────────────
    "Nuapada":       ["Kalahandi", "Balangir", "Bargarh"],
    "Kalahandi":     ["Balangir", "Nuapada", "Koraput", "Nabarangpur"],
    "Nabarangpur":   ["Koraput", "Kalahandi"],
    "Malkangiri":    ["Koraput"],

    # ── South ─────────────────────────────────────────────────────────────────
    "Koraput":       ["Rayagada", "Malkangiri", "Nabarangpur", "Kalahandi"],
    "Rayagada":      ["Koraput", "Kalahandi", "Kandhamal", "Gajapati"],
    "Kandhamal":     ["Balangir", "Boudh", "Nayagarh", "Ganjam", "Gajapati", "Rayagada"],
    "Nayagarh":      ["Khordha", "Cuttack", "Ganjam", "Kandhamal", "Boudh", "Puri"],
    "Gajapati":      ["Ganjam", "Kandhamal", "Rayagada"],
    "Ganjam":        ["Gajapati", "Kandhamal", "Nayagarh", "Puri"],
}

# ── Weather city name aliases ──────────────────────────────────────────────────
WEATHER_CITY_MAP: Dict[str, str] = {
    "konark": "Puri", "chandrabhaga": "Puri", "balighai": "Puri",
    "raghurajpur": "Puri", "puri beach": "Puri", "satapada": "Puri",
    "dhauli": "Bhubaneswar", "khandagiri": "Bhubaneswar", "lingaraj": "Bhubaneswar",
    "nandankanan": "Bhubaneswar", "pipili": "Bhubaneswar",
    "udayagiri": "Nayagarh",
    "jobra": "Cuttack", "ansupa": "Cuttack", "athgarh": "Cuttack",
    "ratnagiri": "Jajpur", "lalitgiri": "Jajpur", "langudi": "Jajpur",
    "chilika": "Berhampur", "rambha": "Berhampur", "gopalpur": "Berhampur",
    "taptapani": "Berhampur", "chatrapur": "Berhampur", "brahmapur": "Berhampur",
    "daringbadi": "Phulbani", "phulbani": "Phulbani",
    "tikarpada": "Angul", "satkosia": "Angul",
    "kapilash": "Dhenkanal", "joranda": "Dhenkanal",
    "bhitarkanika": "Kendrapara", "paradip": "Kendrapara",
    "simlipal": "Baripada", "barehipani": "Baripada",
    "panchalingeswar": "Balasore", "chandipur": "Balasore", "talasari": "Balasore",
    "hirakud": "Sambalpur", "debrigarh": "Sambalpur", "huma": "Sambalpur",
    "bonai": "Rourkela", "sundergarh": "Rourkela",
    "gupteswar": "Koraput", "jeypore": "Koraput", "duduma": "Koraput",
    "deomali": "Koraput",
    "bhubaneswar": "Bhubaneswar", "puri": "Puri", "cuttack": "Cuttack",
    "berhampur": "Berhampur", "sambalpur": "Sambalpur", "rourkela": "Rourkela",
    "baripada": "Baripada", "koraput": "Koraput", "balasore": "Balasore",
    "keonjhar": "Keonjhar", "jharsuguda": "Jharsuguda",
}
