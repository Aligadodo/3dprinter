"""Beer-Lambert optical blending simulation for stacked filament layers.

Physical model:
    Light passes through stacked semi-transparent PLA layers from bottom to top.
    Each layer attenuates some wavelengths and adds its own color.

    transmission = 10^(-thickness / TD)

    At each layer:
        transmitted_light = incident_light * transmission
        added_color = filament_color * (1 - transmission)
        outgoing = transmitted_light + added_color

Reference: Kromacut (vycdev/Kromacut), HueForge
"""

import numpy as np


def beer_lambert_transmission(thickness_mm, td_mm):
    """Calculate light transmission fraction through a filament layer.

    Args:
        thickness_mm: Layer thickness in mm.
        td_mm: Transmission Distance of the filament (mm).

    Returns:
        float [0, 1]: fraction of light that passes through.
    """
    return 10.0 ** (-thickness_mm / max(td_mm, 0.01))


def hex_to_rgb(hex_color):
    """Convert hex color string to normalized RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16) / 255.0,
        int(hex_color[2:4], 16) / 255.0,
        int(hex_color[4:6], 16) / 255.0,
    )


def rgb_to_lab(rgb):
    """Convert linear RGB [0,1]³ to CIE L*a*b* for perceptual comparison.

    Uses D65 illuminant, sRGB primaries.
    """
    # sRGB linearization
    def _linearize(c):
        if c <= 0.04045:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    r_lin = _linearize(rgb[0])
    g_lin = _linearize(rgb[1])
    b_lin = _linearize(rgb[2])

    # sRGB → XYZ (D65)
    x = 0.4124564 * r_lin + 0.3575761 * g_lin + 0.1804375 * b_lin
    y = 0.2126729 * r_lin + 0.7151522 * g_lin + 0.0721750 * b_lin
    z = 0.0193339 * r_lin + 0.1191920 * g_lin + 0.9503041 * b_lin

    # XYZ → Lab (D65 reference: Xn=0.95047, Yn=1.0, Zn=1.08883)
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def _f(t):
        delta = 6.0 / 29.0
        if t > delta ** 3:
            return t ** (1.0 / 3.0)
        return t / (3.0 * delta ** 2) + 4.0 / 29.0

    fy = _f(y / yn)
    L = 116.0 * fy - 16.0
    a = 500.0 * (_f(x / xn) - fy)
    b = 200.0 * (fy - _f(z / zn))

    return np.array([L, a, b])


def rgb_to_lab_batch(rgb):
    """Vectorized RGB [0,1]^3 → CIE L*a*b* for arrays of pixels.

    Args:
        rgb: (N, 3) float array, values in [0, 1].

    Returns:
        (N, 3) float array of L*a*b* values.
    """
    # sRGB linearization
    mask = rgb <= 0.04045
    lin = np.empty_like(rgb, dtype=np.float64)
    lin[mask] = rgb[mask] / 12.92
    lin[~mask] = ((rgb[~mask] + 0.055) / 1.055) ** 2.4

    # sRGB → XYZ (D65)
    x = 0.4124564 * lin[:, 0] + 0.3575761 * lin[:, 1] + 0.1804375 * lin[:, 2]
    y = 0.2126729 * lin[:, 0] + 0.7151522 * lin[:, 1] + 0.0721750 * lin[:, 2]
    z = 0.0193339 * lin[:, 0] + 0.1191920 * lin[:, 1] + 0.9503041 * lin[:, 2]

    # XYZ → Lab (D65 reference)
    xn, yn, zn = 0.95047, 1.0, 1.08883
    delta = 6.0 / 29.0
    delta3 = delta ** 3

    def _f(t):
        out = np.empty_like(t, dtype=np.float64)
        hi = t > delta3
        out[hi] = t[hi] ** (1.0 / 3.0)
        out[~hi] = t[~hi] / (3.0 * delta ** 2) + 4.0 / 29.0
        return out

    fy = _f(y / yn)
    L = 116.0 * fy - 16.0
    a = 500.0 * (_f(x / xn) - fy)
    b = 200.0 * (fy - _f(z / zn))

    return np.column_stack([L, a, b])


def delta_e_2000(lab1, lab2):
    """CIEDE2000 color difference formula — perceptually uniform.

    Args:
        lab1, lab2: CIE L*a*b* arrays.

    Returns:
        float: perceptual color difference. < 1.0 = imperceptible,
               < 2.3 = just noticeable difference (JND).
    """
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    L_bar = (L1 + L2) / 2.0
    C1 = np.sqrt(a1 ** 2 + b1 ** 2)
    C2 = np.sqrt(a2 ** 2 + b2 ** 2)
    C_bar = (C1 + C2) / 2.0

    # G factor
    C_bar_7 = C_bar ** 7
    G = 0.5 * (1.0 - np.sqrt(C_bar_7 / (C_bar_7 + 25.0 ** 7)))

    a1_p = a1 * (1.0 + G)
    a2_p = a2 * (1.0 + G)

    C1_p = np.sqrt(a1_p ** 2 + b1 ** 2)
    C2_p = np.sqrt(a2_p ** 2 + b2 ** 2)
    C_bar_p = (C1_p + C2_p) / 2.0

    h1_p = np.degrees(np.arctan2(b1, a1_p)) % 360.0
    h2_p = np.degrees(np.arctan2(b2, a2_p)) % 360.0

    if abs(h1_p - h2_p) <= 180.0:
        H_bar_p = (h1_p + h2_p) / 2.0
    else:
        H_bar_p = (h1_p + h2_p + 360.0) / 2.0

    T = (1.0 - 0.17 * np.cos(np.radians(H_bar_p - 30.0))
         + 0.24 * np.cos(np.radians(2.0 * H_bar_p))
         + 0.32 * np.cos(np.radians(3.0 * H_bar_p + 6.0))
         - 0.20 * np.cos(np.radians(4.0 * H_bar_p - 63.0)))

    dh = abs(h1_p - h2_p)
    if dh > 180.0:
        dh = 360.0 - dh
    delta_h_p = 2.0 * np.sqrt(C1_p * C2_p) * np.sin(np.radians(dh / 2.0))

    delta_L_p = L2 - L1
    delta_C_p = C2_p - C1_p

    S_L = 1.0 + (0.015 * (L_bar - 50.0) ** 2) / np.sqrt(20.0 + (L_bar - 50.0) ** 2)
    S_C = 1.0 + 0.045 * C_bar_p
    S_H = 1.0 + 0.015 * C_bar_p * T

    delta_theta = 30.0 * np.exp(-((H_bar_p - 275.0) / 25.0) ** 2)
    R_C = 2.0 * np.sqrt(C_bar_p ** 7 / (C_bar_p ** 7 + 25.0 ** 7))
    R_T = -R_C * np.sin(2.0 * np.radians(delta_theta))

    k_L = k_C = k_H = 1.0

    term1 = delta_L_p / (k_L * S_L)
    term2 = delta_C_p / (k_C * S_C)
    term3 = delta_h_p / (k_H * S_H)

    return np.sqrt(term1 ** 2 + term2 ** 2 + term3 ** 2 + R_T * term2 * term3)


def beer_lambert_blend(layer_stack, layer_height=0.08):
    """Simulate light passing through a stack of filament layers.

    Light enters from the BACK (bottom layer), travels through each layer,
    and the resulting color is what an observer on the FRONT (top surface) sees.

    Args:
        layer_stack: List of (filament_dict, thickness_mm) tuples, bottom to top.
            filament_dict must have keys: "color" (hex str), "td" (float).
        layer_height: mm per individual layer (for sub-step simulation accuracy).

    Returns:
        (r, g, b): Normalized RGB tuple [0, 1]³ of the blended result.
    """
    # Start with white light entering from the back
    light = np.array([1.0, 1.0, 1.0], dtype=np.float64)

    for filament, thickness in layer_stack:
        td = max(filament.get("td", 4.0), 0.01)
        filament_rgb = np.array(hex_to_rgb(filament["color"]), dtype=np.float64)

        # Subdivide thickness into individual layers for accuracy
        n_steps = max(1, int(thickness / layer_height + 0.5))
        step_thickness = thickness / n_steps

        for _ in range(n_steps):
            transmission = np.float64(10.0 ** (-step_thickness / td))
            # Each sub-layer: light is partially transmitted, partially absorbed/replaced
            light = light * transmission + filament_rgb * (1.0 - transmission)

    return (float(light[0]), float(light[1]), float(light[2]))


def compute_opacity(thickness_mm, td_mm):
    """Compute how opaque a filament layer is.

    Returns:
        float [0, 1]: 0 = fully transparent, 1 = fully opaque.
    """
    transmission = beer_lambert_transmission(thickness_mm, td_mm)
    return 1.0 - transmission


def generate_virtual_swatches(ordered_filaments, layer_assignments, layer_height=0.08):
    """Generate color swatches for all possible Z-heights in the layer stack.

    Each swatch records: z height, blended color (RGB), and which filament
    is the topmost at that height.

    Args:
        ordered_filaments: List of filament dicts, bottom-to-top order.
        layer_assignments: List of dicts with keys:
            filament_index, start_z, thickness.
        layer_height: mm per individual sub-layer.

    Returns:
        List of dicts: {z_mm, rgb, top_filament_index}
    """
    swatches = []
    current_z = 0.0

    for assignment in layer_assignments:
        fil_idx = assignment["filament_index"]
        thickness = assignment["thickness"]
        n_steps = max(1, int(thickness / layer_height + 0.5))
        step = thickness / n_steps

        for s in range(n_steps):
            sample_z = current_z + (s + 0.5) * step

            # Build the layer stack up to sample_z
            stack = _build_stack_up_to(
                ordered_filaments, layer_assignments, sample_z, layer_height)

            blended = beer_lambert_blend(stack, layer_height)

            swatches.append({
                "z_mm": round(sample_z, 4),
                "rgb": blended,
                "top_filament_index": fil_idx,
            })

        current_z += thickness

    return swatches


def _build_stack_up_to(filaments, assignments, target_z, layer_height):
    """Build layer stack from bottom up to target_z height."""
    stack = []
    current_z = 0.0

    for assignment in assignments:
        thickness = assignment["thickness"]
        next_z = current_z + thickness

        if next_z <= target_z:
            stack.append((filaments[assignment["filament_index"]], thickness))
        elif current_z < target_z:
            partial_thickness = target_z - current_z
            stack.append((filaments[assignment["filament_index"]], partial_thickness))
            break
        else:
            break

        current_z = next_z

    return stack


def match_pixel_to_swatch(pixel_rgb, swatches):
    """Find the swatch whose blended color best matches the target pixel.

    Args:
        pixel_rgb: (R, G, B) normalized [0, 1].
        swatches: List from generate_virtual_swatches().

    Returns:
        swatch dict with closest color match.
    """
    target_lab = rgb_to_lab(pixel_rgb)
    best_swatch = None
    best_de = float("inf")

    for swatch in swatches:
        swatch_lab = rgb_to_lab(swatch["rgb"])
        de = delta_e_2000(target_lab, swatch_lab)
        if de < best_de:
            best_de = de
            best_swatch = swatch

    return best_swatch
