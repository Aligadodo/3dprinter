"""Filament stacking order optimization.

Finds the optimal bottom-to-top filament ordering that:
  1. Minimizes perceptual color error (DeltaE 2000) against target image.
  2. Keeps total Z-height within budget.
  3. Produces stable transition zones between adjacent colors.

Algorithms:
  - Exhaustive search: ≤4 filaments, evaluates all n! permutations.
  - Simulated annealing: 5+ filaments, physics-inspired probabilistic search.

Reference: Kromacut (vycdev/Kromacut) — exhaustive + SA + genetic optimizer.
"""

import math
import random
import numpy as np

from .color_blending import (
    beer_lambert_blend,
    beer_lambert_transmission,
    delta_e_2000,
    hex_to_rgb,
    rgb_to_lab,
    compute_opacity,
)


# Convergence thresholds (from Kromacut)
DELTA_E_JND = 2.3       # Just Noticeable Difference — converged
OPACITY_CONVERGED = 0.85  # 85% opaque = effectively solid
FOUNDATION_FACTOR = 1.3   # Extra thickness for base layer (~95% opaque)


def optimize_layer_stack(filaments, image_rgb, layer_height=0.08,
                         max_thickness_mm=3.0, region_weight="uniform",
                         max_extra_swaps=0):
    """Find the optimal filament stacking order and per-color thicknesses.

    Args:
        filaments: List of dicts {name, color, td}.
        image_rgb: H×W×3 float array [0, 255] of target image.
        layer_height: mm per printed layer (default 0.08).
        max_thickness_mm: Maximum total blend height budget.
        region_weight: "uniform", "center", or "edge".
        max_extra_swaps: Allow repeated filament use (0 = each color once).

    Returns:
        dict with keys:
            ordered_filaments: list of filament dicts, bottom→top.
            layer_assignments: list of {filament_index, start_z, thickness}.
            total_height: total blend zone thickness (mm).
            score: quality score (lower = better).
    """
    n = len(filaments)
    if n == 0:
        return {"ordered_filaments": [], "layer_assignments": [], "total_height": 0.0, "score": 0.0}
    if n == 1:
        return _single_filament_plan(filaments, max_thickness_mm)

    # Generate pixel samples for scoring
    max_samples = 200 if n >= 5 else 2000  # fewer samples for SA path
    sample_pixels = _sample_pixels(image_rgb, region_weight, max_samples=max_samples)

    if n <= 4:
        return _exhaustive_search(filaments, sample_pixels, layer_height,
                                  max_thickness_mm, max_extra_swaps)
    else:
        return _simulated_annealing(filaments, sample_pixels, layer_height,
                                    max_thickness_mm, max_extra_swaps)


def _single_filament_plan(filaments, max_thickness):
    """Trivial plan for single-filament (monochrome)."""
    f = filaments[0]
    thickness = min(f["td"] * FOUNDATION_FACTOR, max_thickness)
    return {
        "ordered_filaments": list(filaments),
        "layer_assignments": [{"filament_index": 0, "start_z": 0.0, "thickness": thickness}],
        "total_height": thickness,
        "score": 0.0,
    }


def _exhaustive_search(filaments, sample_pixels, layer_height, max_thickness,
                       max_extra_swaps):
    """Evaluate all n! filament orderings, return the best."""
    import itertools

    best_result = None
    best_score = float("inf")
    indices = list(range(len(filaments)))

    for perm in itertools.permutations(indices):
        ordered = [filaments[i] for i in perm]
        result = _build_layer_plan(ordered, sample_pixels, layer_height,
                                   max_thickness, max_extra_swaps)
        if result["score"] < best_score:
            best_score = result["score"]
            best_result = result

    return best_result


def _simulated_annealing(filaments, sample_pixels, layer_height, max_thickness,
                         max_extra_swaps, iterations=500):
    """Simulated annealing search for optimal filament ordering.

    Starts from luminance-sorted order (dark bottom → light top).
    Cooling schedule: T = T0 * alpha^k, alpha ≈ 0.995
    """
    n = len(filaments)
    # Start from luminance-sorted order (physically plausible default)
    lum_order = sorted(range(n), key=lambda i: _filament_luminance(filaments[i]))
    current_order = list(lum_order)
    current_ordered = [filaments[i] for i in current_order]

    current_result = _build_layer_plan(current_ordered, sample_pixels,
                                       layer_height, max_thickness, max_extra_swaps)
    current_score = current_result["score"]

    best_result = current_result
    best_score = current_score

    T0 = 10.0
    T_min = 0.01
    alpha = 0.995
    T = T0

    for _ in range(iterations):
        if T < T_min:
            break

        # Neighbor: swap two random positions
        new_order = list(current_order)
        i, j = random.sample(range(n), 2)
        new_order[i], new_order[j] = new_order[j], new_order[i]
        new_ordered = [filaments[k] for k in new_order]

        new_result = _build_layer_plan(new_ordered, sample_pixels,
                                       layer_height, max_thickness, max_extra_swaps)
        new_score = new_result["score"]

        delta = new_score - current_score

        if delta < 0 or random.random() < math.exp(-delta / T):
            current_order = new_order
            current_score = new_score
            current_result = new_result

            if current_score < best_score:
                best_score = current_score
                best_result = current_result

        T *= alpha

    return best_result


def _build_layer_plan(ordered_filaments, sample_pixels, layer_height,
                      max_thickness, max_extra_swaps):
    """Compute transition zones and thickness for a given filament ordering.

    Strategy:
      1. Foundation zone for bottom filament: TD × 1.3 (~95% opaque).
      2. For each subsequent filament pair, compute transition zone:
         - Simulate adding layers of the next filament until blended color
           converges (DeltaE < 2.3) to the pure next-filament color.
      3. If total height exceeds max_thickness, compress proportionally.
    """
    assignments = []
    total_height = 0.0

    # Foundation zone for the bottom (darkest) filament
    bottom = ordered_filaments[0]
    foundation_thickness = bottom["td"] * FOUNDATION_FACTOR
    foundation_thickness = min(foundation_thickness, max_thickness * 0.4)

    # Snap to layer height
    n_layers = max(1, int(foundation_thickness / layer_height + 0.5))
    foundation_thickness = n_layers * layer_height

    assignments.append({
        "filament_index": 0,
        "start_z": 0.0,
        "thickness": foundation_thickness,
    })
    total_height = foundation_thickness

    # Transition zones for each subsequent filament
    for i in range(1, len(ordered_filaments)):
        remaining_budget = max_thickness - total_height
        if remaining_budget <= layer_height:
            break

        this_fil = ordered_filaments[i]

        transition_thickness = _compute_transition_zone(
            ordered_filaments[:i], this_fil, layer_height, remaining_budget)

        if transition_thickness > 0:
            assignments.append({
                "filament_index": i,
                "start_z": total_height,
                "thickness": transition_thickness,
            })
            total_height += transition_thickness

    # Top filament gets remaining budget for pure color zone
    if total_height < max_thickness and len(ordered_filaments) > 0:
        remaining = max_thickness - total_height
        n_layers = int(remaining / layer_height + 0.5)
        if n_layers > 0:
            top_thickness = n_layers * layer_height
            # Check if last assignment is already the top filament
            if assignments and assignments[-1]["filament_index"] == len(ordered_filaments) - 1:
                assignments[-1]["thickness"] += top_thickness
            else:
                assignments.append({
                    "filament_index": len(ordered_filaments) - 1,
                    "start_z": total_height,
                    "thickness": top_thickness,
                })
            total_height += top_thickness

    # Score this plan
    score = _score_plan(ordered_filaments, assignments, sample_pixels, layer_height)

    return {
        "ordered_filaments": ordered_filaments,
        "layer_assignments": assignments,
        "total_height": total_height,
        "score": score,
    }


def _compute_transition_zone(below_filaments, top_filament, layer_height,
                             max_budget):
    """Compute how many layers of top_filament are needed to converge.

    Convergence: the blended color of (below_stack + N layers of top) is
    visually indistinguishable from pure top_filament color (DeltaE < 2.3),
    OR the composite reaches 85% opacity.

    Returns thickness in mm (snapped to layer_height increments).
    """
    top_rgb = np.array(hex_to_rgb(top_filament["color"]), dtype=np.float64)
    top_lab = rgb_to_lab(top_rgb)
    top_td = max(top_filament.get("td", 4.0), 0.01)

    thickness = 0.0
    max_layers = int(max_budget / layer_height)

    for n in range(1, max_layers + 1):
        thickness = n * layer_height

        # Build stack: all below filaments + N layers of top
        stack = [(f, f["td"] * FOUNDATION_FACTOR) for f in below_filaments]  # approx
        # More accurate: use the actual below thicknesses
        blended = _blend_stack_with_top(below_filaments, top_filament,
                                        thickness, layer_height)
        blended_lab = rgb_to_lab(blended)
        de = delta_e_2000(top_lab, blended_lab)

        # Check opacity convergence
        composite_opacity = _composite_opacity(below_filaments, top_filament,
                                               thickness, layer_height)

        if de < DELTA_E_JND or composite_opacity > OPACITY_CONVERGED:
            return thickness

    # Couldn't converge within budget — return max
    return thickness if thickness > 0 else layer_height


def _blend_stack_with_top(below_filaments, top_filament, top_thickness,
                          layer_height):
    """Simulate blending of below stack + top filament layers."""
    from .color_blending import beer_lambert_blend as bl_blend

    # Approximate below stack: each filament at its foundation thickness
    stack = []
    for f in below_filaments:
        stack.append((f, f["td"] * 0.5))  # simplified below representation

    stack.append((top_filament, top_thickness))
    return bl_blend(stack, layer_height)


def _composite_opacity(filaments_below, top_filament, top_thickness,
                       layer_height):
    """Compute composite opacity of the full stack."""
    total_opacity = 0.0
    remaining_light = 1.0

    # Simplified: treat all below as one block
    for f in filaments_below:
        t = f["td"] * 0.5  # simplified
        tr = beer_lambert_transmission(t, max(f.get("td", 4.0), 0.01))
        remaining_light *= tr

    tr_top = beer_lambert_transmission(top_thickness,
                                       max(top_filament.get("td", 4.0), 0.01))
    remaining_light *= tr_top

    return 1.0 - remaining_light


def _score_plan(ordered_filaments, assignments, sample_pixels, layer_height):
    """Score a layer plan by color matching error on sample pixels.

    Lower score = better match.
    Penalizes physically implausible orderings (light/transparent on bottom,
    dark/opaque on top).
    """
    from .color_blending import generate_virtual_swatches, match_pixel_to_swatch

    swatches = generate_virtual_swatches(ordered_filaments, assignments,
                                         layer_height)
    if not swatches:
        return float("inf")

    total_de = 0.0
    for pixel_rgb in sample_pixels:
        best = match_pixel_to_swatch(pixel_rgb, swatches)
        if best:
            pixel_lab = rgb_to_lab(pixel_rgb)
            swatch_lab = rgb_to_lab(best["rgb"])
            total_de += delta_e_2000(pixel_lab, swatch_lab)

    avg_de = total_de / len(sample_pixels)

    # Height penalty
    height_penalty = 0.0
    if ordered_filaments:
        ideal_height = sum(f["td"] * FOUNDATION_FACTOR for f in ordered_filaments) * 0.5
        actual_height = sum(a["thickness"] for a in assignments)
        height_penalty = abs(actual_height - ideal_height) * 0.01

    # Luminance ordering penalty: darker should be on bottom
    # Light-on-bottom blocks visibility of darker layers above
    luminance_penalty = 0.0
    if len(ordered_filaments) >= 2:
        lums = [_filament_luminance(f) for f in ordered_filaments]
        for i in range(len(lums) - 1):
            if lums[i] > lums[i + 1]:
                # Brighter filament below darker one — physically wrong
                # Strong penalty: bright-under-dark is physically wrong
                # (dark filament on top blocks all light from below)
                luminance_penalty += (lums[i] - lums[i + 1]) * 50.0 + 5.0

    return avg_de + height_penalty + luminance_penalty


def _filament_luminance(filament):
    """Compute perceived luminance of a filament color in [0, 1]."""
    rgb = hex_to_rgb(filament["color"])
    # ITU-R BT.709 perceptual weights
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _sample_pixels(image_rgb, region_weight="uniform", max_samples=2000):
    """Extract representative pixel samples weighted by region importance.

    Args:
        image_rgb: H×W×3 float array [0, 255].
        region_weight: "uniform", "center", or "edge".
        max_samples: maximum number of sample pixels.

    Returns:
        List of (R, G, B) normalized tuples.
    """
    H, W = image_rgb.shape[:2]
    pixels = image_rgb.reshape(-1, 3) / 255.0

    # Use stratified sampling for speed
    n_pixels = H * W
    if n_pixels <= max_samples:
        indices = range(n_pixels)
    else:
        indices = np.random.choice(n_pixels, max_samples, replace=False)

    if region_weight == "uniform":
        return [tuple(pixels[i]) for i in indices]

    # Build weight map
    if region_weight == "center":
        y, x = np.mgrid[0:H, 0:W]
        cx, cy = W / 2, H / 2
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        sigma = min(W, H) / 3.0
        weights = np.exp(-0.5 * (dist / sigma) ** 2).ravel()
    elif region_weight == "edge":
        # Sobel edge detection
        gray = 0.299 * image_rgb[:, :, 0] + 0.587 * image_rgb[:, :, 1] + 0.114 * image_rgb[:, :, 2]
        from scipy.ndimage import sobel
        edges = np.sqrt(sobel(gray, axis=0) ** 2 + sobel(gray, axis=1) ** 2)
        weights = edges.ravel()
        weights = weights / (weights.max() + 1e-10) + 0.1  # small baseline
    else:
        return [tuple(pixels[i]) for i in indices]

    # Weighted sampling
    weights = weights / weights.sum()
    weighted_indices = np.random.choice(n_pixels, min(max_samples, n_pixels),
                                        replace=False, p=weights)
    return [tuple(pixels[i]) for i in weighted_indices]
