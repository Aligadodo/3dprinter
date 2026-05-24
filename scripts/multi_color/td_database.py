"""Known Transmission Distance (TD) values for common filament brands.

TD = thickness (mm) at which ~90% of light is blocked (~10% transmitted).
Lower TD = more opaque. Higher TD = more translucent.

Values sourced from HueForge community database and manufacturer specs.
"""

# Primary database: (brand, color_name) → TD (mm)
# Brand matching is case-insensitive, partial match.
KNOWN_TD = {
    # ── Bambu Lab PLA Basic ──
    ("bambu", "black"): 0.6,
    ("bambu", "charcoal"): 0.8,
    ("bambu", "dark brown"): 0.9,
    ("bambu", "brown"): 1.2,
    ("bambu", "dark blue"): 1.0,
    ("bambu", "blue"): 2.8,
    ("bambu", "blue gray"): 3.1,
    ("bambu", "gray"): 1.5,
    ("bambu", "light gray"): 3.0,
    ("bambu", "silver"): 2.5,
    ("bambu", "dark green"): 1.0,
    ("bambu", "green"): 2.5,
    ("bambu", "lime green"): 4.5,
    ("bambu", "mint green"): 4.0,
    ("bambu", "dark red"): 1.0,
    ("bambu", "red"): 3.5,
    ("bambu", "crimson"): 2.5,
    ("bambu", "orange"): 4.0,
    ("bambu", "yellow"): 5.5,
    ("bambu", "gold"): 3.5,
    ("bambu", "purple"): 2.5,
    ("bambu", "magenta"): 3.0,
    ("bambu", "pink"): 4.0,
    ("bambu", "cyan"): 4.5,
    ("bambu", "white"): 4.4,
    ("bambu", "jade white"): 5.0,
    ("bambu", "ivory white"): 5.5,
    ("bambu", "beige"): 4.0,
    ("bambu", "natural"): 6.0,

    # ── Bambu Lab PLA Matte ──
    ("bambu matte", "black"): 0.4,
    ("bambu matte", "charcoal"): 0.5,
    ("bambu matte", "dark brown"): 0.8,
    ("bambu matte", "dark blue"): 0.8,
    ("bambu matte", "blue"): 2.5,
    ("bambu matte", "gray"): 1.2,
    ("bambu matte", "light gray"): 2.8,
    ("bambu matte", "dark green"): 0.8,
    ("bambu matte", "green"): 2.2,
    ("bambu matte", "dark red"): 1.0,
    ("bambu matte", "red"): 3.0,
    ("bambu matte", "orange"): 3.5,
    ("bambu matte", "yellow"): 5.0,
    ("bambu matte", "purple"): 2.2,
    ("bambu matte", "magenta"): 2.8,
    ("bambu matte", "pink"): 3.5,
    ("bambu matte", "white"): 3.5,
    ("bambu matte", "ivory white"): 4.5,
    ("bambu matte", "beige"): 3.5,

    # ── Bambu Lab PLA Silk ──
    ("bambu silk", "silver"): 1.0,
    ("bambu silk", "gold"): 1.2,
    ("bambu silk", "copper"): 0.8,
    ("bambu silk", "white"): 2.5,

    # ── Polymaker PolyTerra PLA ──
    ("polymaker", "black"): 0.5,
    ("polymaker", "charcoal"): 0.8,
    ("polymaker", "dark brown"): 1.0,
    ("polymaker", "brown"): 1.5,
    ("polymaker", "navy blue"): 1.0,
    ("polymaker", "blue"): 3.0,
    ("polymaker", "gray"): 1.5,
    ("polymaker", "light gray"): 3.5,
    ("polymaker", "dark green"): 1.0,
    ("polymaker", "green"): 2.8,
    ("polymaker", "lime green"): 5.0,
    ("polymaker", "dark red"): 1.2,
    ("polymaker", "red"): 3.5,
    ("polymaker", "orange"): 4.5,
    ("polymaker", "yellow"): 6.0,
    ("polymaker", "purple"): 2.8,
    ("polymaker", "pink"): 4.5,
    ("polymaker", "cyan"): 5.0,
    ("polymaker", "white"): 4.5,
    ("polymaker", "beige"): 4.0,

    # ── Sunlu PLA ──
    ("sunlu", "black"): 0.7,
    ("sunlu", "gray"): 1.8,
    ("sunlu", "blue"): 3.2,
    ("sunlu", "red"): 3.5,
    ("sunlu", "green"): 3.0,
    ("sunlu", "yellow"): 5.5,
    ("sunlu", "orange"): 4.5,
    ("sunlu", "white"): 4.5,

    # ── eSun PLA+ ──
    ("esun", "black"): 0.5,
    ("esun", "gray"): 1.5,
    ("esun", "dark blue"): 1.0,
    ("esun", "blue"): 3.0,
    ("esun", "red"): 3.5,
    ("esun", "green"): 2.8,
    ("esun", "yellow"): 5.0,
    ("esun", "orange"): 4.0,
    ("esun", "white"): 4.0,
    ("esun", "natural"): 5.5,

    # ── Generic / Unknown PLA (conservative estimates) ──
    ("generic", "black"): 0.6,
    ("generic", "dark gray"): 1.0,
    ("generic", "gray"): 1.8,
    ("generic", "light gray"): 3.0,
    ("generic", "dark blue"): 1.0,
    ("generic", "blue"): 3.0,
    ("generic", "cyan"): 4.5,
    ("generic", "dark green"): 1.0,
    ("generic", "green"): 2.8,
    ("generic", "dark red"): 1.2,
    ("generic", "red"): 3.5,
    ("generic", "orange"): 4.2,
    ("generic", "yellow"): 5.0,
    ("generic", "purple"): 2.8,
    ("generic", "magenta"): 3.2,
    ("generic", "pink"): 4.0,
    ("generic", "brown"): 1.5,
    ("generic", "white"): 4.5,
    ("generic", "natural"): 5.5,

    # ── PETG (generally more translucent than PLA) ──
    ("petg", "black"): 0.8,
    ("petg", "gray"): 2.5,
    ("petg", "blue"): 4.0,
    ("petg", "red"): 4.5,
    ("petg", "green"): 4.0,
    ("petg", "yellow"): 7.0,
    ("petg", "orange"): 5.5,
    ("petg", "white"): 5.5,
    ("petg", "natural"): 7.5,
    ("petg", "transparent"): 12.0,
}


def lookup_td(brand_or_name, color_name=None):
    """Look up TD value for a filament, with fuzzy matching.

    Args:
        brand_or_name: Brand name (e.g. "Bambu Lab PLA Basic")
                       or combined string (e.g. "Bambu Basic Black PLA").
        color_name: Color name. If None, attempt to extract from brand_or_name.

    Returns:
        TD value in mm (float). Returns 4.0 as a conservative default if
        no match found.
    """
    search_brand = brand_or_name.lower().strip()
    search_color = (color_name or "").lower().strip()

    # If no separate color, try to split brand_or_name into brand + color
    if not search_color:
        for color_key in _COLOR_NAMES:
            if color_key in search_brand:
                search_color = color_key
                # Remove color from brand string
                search_brand = search_brand.replace(color_key, "").strip()
                break

    if not search_color:
        # Try to guess color from the string
        for color_key in _COLOR_NAMES:
            if color_key in search_brand:
                search_color = color_key
                break

    if not search_color:
        return 4.0  # conservative default

    # Match brand
    for (db_brand, db_color), td in KNOWN_TD.items():
        if db_brand in search_brand or search_brand in db_brand:
            if db_color == search_color:
                return td

    # Match color only (generic)
    for (db_brand, db_color), td in KNOWN_TD.items():
        if db_brand == "generic" and db_color == search_color:
            return td

    # Fuzzy color match
    for (db_brand, db_color), td in KNOWN_TD.items():
        if db_color in search_color or search_color in db_color:
            return td

    # Estimate TD from color luminance as last resort
    return _estimate_td_from_color(search_color)


_COLOR_NAMES = [
    "black", "charcoal", "dark brown", "brown", "navy blue", "dark blue",
    "blue", "blue gray", "light blue", "gray", "light gray", "silver",
    "dark green", "green", "lime green", "mint green", "dark red", "red",
    "crimson", "orange", "yellow", "gold", "copper", "purple", "magenta",
    "pink", "cyan", "white", "jade white", "ivory white", "beige",
    "natural", "transparent",
]

# Approximate sRGB values for color names (used for palette→filament matching)
_COLOR_RGB = {
    "black":       (15, 15, 15),
    "charcoal":    (54, 69, 79),
    "dark brown":  (60, 30, 20),
    "brown":       (120, 70, 40),
    "navy blue":   (20, 20, 80),
    "dark blue":   (20, 40, 130),
    "blue":        (30, 80, 200),
    "blue gray":   (100, 120, 150),
    "light blue":  (150, 190, 230),
    "gray":        (128, 128, 128),
    "light gray":  (190, 190, 190),
    "silver":      (192, 192, 196),
    "dark green":  (20, 80, 30),
    "green":       (30, 150, 60),
    "lime green":  (50, 205, 50),
    "mint green":  (150, 230, 180),
    "dark red":    (130, 20, 20),
    "red":         (210, 40, 40),
    "crimson":     (180, 20, 50),
    "orange":      (240, 130, 30),
    "yellow":      (245, 220, 30),
    "gold":        (212, 175, 55),
    "copper":      (180, 110, 50),
    "purple":      (130, 50, 180),
    "magenta":     (210, 30, 140),
    "pink":        (240, 150, 180),
    "cyan":        (30, 200, 210),
    "white":       (245, 245, 245),
    "jade white":  (235, 238, 225),
    "ivory white": (245, 240, 225),
    "beige":       (225, 210, 180),
    "natural":     (220, 210, 190),
    "transparent": (250, 250, 250),
}


def find_closest_filaments(rgb_list, preferred_brand=None):
    """Map dominant image colors to the closest known filaments.

    Uses CIEDE2000 perceptual color difference to find the best matching
    filament from the KNOWN_TD database for each extracted color.
    Filaments are returned sorted by luminance (dark→light), the
    physically correct bottom→top stacking order.

    Args:
        rgb_list: List of (R, G, B) tuples, each in [0, 255].
        preferred_brand: Optional brand substring to prefer (e.g. "bambu").

    Returns:
        List of filament dicts: [{color, name, td}], sorted dark→light.
    """
    from .color_blending import delta_e_2000, rgb_to_lab

    # Build reference list: (brand, color_name, td, lab)
    ref_entries = []
    for (brand, color_name), td in KNOWN_TD.items():
        if color_name in _COLOR_RGB:
            ref_rgb = _COLOR_RGB[color_name]
            ref_lab = rgb_to_lab(ref_rgb)
            ref_entries.append((brand, color_name, td, ref_rgb, ref_lab))

    if not ref_entries:
        return _fallback_filaments(rgb_list)

    # Prefer brand if specified
    if preferred_brand:
        preferred = [e for e in ref_entries if preferred_brand.lower() in e[0]]
        if preferred:
            ref_entries = preferred

    result = []
    for rgb in rgb_list:
        target_lab = rgb_to_lab(rgb)

        best_entry = None
        best_de = float("inf")
        for brand, cname, td, ref_rgb, ref_lab in ref_entries:
            de = delta_e_2000(target_lab, ref_lab)
            if de < best_de:
                best_de = de
                best_entry = (brand, cname, td, ref_rgb)

        if best_entry:
            brand, cname, td, ref_rgb = best_entry
            hex_color = f"#{ref_rgb[0]:02x}{ref_rgb[1]:02x}{ref_rgb[2]:02x}"
            display_name = f"{brand.title()} {cname.title()}"
            result.append({"color": hex_color, "name": display_name, "td": td})
        else:
            # Fallback: use the extracted RGB directly with estimated TD
            hex_color = f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"
            result.append({"color": hex_color, "name": f"Color #{hex_color}", "td": 4.0})

    # Deduplicate: if multiple input colors map to same filament, keep only first
    seen_names = set()
    deduped = []
    for f in result:
        if f["name"] not in seen_names:
            seen_names.add(f["name"])
            deduped.append(f)

    # Sort by luminance: dark → light (bottom → top)
    deduped.sort(key=lambda f: (
        0.2126 * int(f["color"][1:3], 16) +
        0.7152 * int(f["color"][3:5], 16) +
        0.0722 * int(f["color"][5:7], 16)
    ))

    return deduped


def _fallback_filaments(rgb_list):
    """Minimal fallback when database has no RGB references."""
    result = []
    for rgb in rgb_list:
        hex_color = f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"
        result.append({"color": hex_color, "name": f"Color #{hex_color}", "td": 4.0})
    return result


def _estimate_td_from_color(color_name):
    """Crude TD estimate based on color semantics."""
    color_name = color_name.lower()
    if any(w in color_name for w in ["black", "charcoal"]):
        return 0.6
    if any(w in color_name for w in ["dark", "navy"]):
        return 1.0
    if any(w in color_name for w in ["gray", "grey", "brown", "silver", "copper", "gold"]):
        return 1.8
    if any(w in color_name for w in ["red", "blue", "green", "purple", "magenta"]):
        return 3.0
    if any(w in color_name for w in ["orange", "pink", "cyan", "beige", "lime"]):
        return 4.5
    if any(w in color_name for w in ["white", "yellow"]):
        return 5.0
    if any(w in color_name for w in ["natural", "transparent"]):
        return 6.5
    return 4.0  # conservative default
