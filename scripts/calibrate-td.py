#!/usr/bin/env python
"""calibrate-td.py - Measure filament Transmission Distance (TD) values.

Generates a test swatch STL with stepped thicknesses, then computes TD from
measured luminance values using exponential regression.

Usage:
  # Step 1: Generate test swatch STL
  python scripts/calibrate-td.py --generate --output calibrate_swatch.stl

  # Step 2: Print the swatch, then measure with a camera/light meter
  #   For each thickness step (0.3, 0.6, 1.0, 1.5, 2.0 mm),
  #   record the luminance (0-255) when backlit.

  # Step 3: Calculate TD from measurements
  python scripts/calibrate-td.py --calculate \\
      --measurements '[[0.3, 200], [0.6, 150], [1.0, 80], [1.5, 35], [2.0, 15]]' \\
      --name "My Red PLA"

  # Step 4: Use the result in multi-color mode
  #   TD = 1.23 → --filaments '[{"color":"#FF0000","td":1.23,"name":"My Red PLA"}]'
"""

import argparse
import json
import os
import sys
import struct
import numpy as np


# ── Step 1: Generate calibration swatch STL ──

def generate_calibration_swatch(output_path, thicknesses=None,
                                swatch_size_mm=(20, 20),
                                base_thickness_mm=0.6):
    """Generate a stepped-thickness test swatch STL for TD measurement.

    The swatch has rectangular steps at increasing thicknesses. Print with
    100% infill, hold against a light source, and measure luminance through
    each step to determine Transmission Distance.

    Args:
        output_path: Output STL file path.
        thicknesses: List of thickness values in mm to test.
                     Default: [0.3, 0.6, 1.0, 1.5, 2.0, 3.0].
        swatch_size_mm: (width, height) of each step in mm.
        base_thickness_mm: Minimum thickness (backing plate).
    """
    if thicknesses is None:
        thicknesses = [0.3, 0.6, 1.0, 1.5, 2.0, 3.0]

    w, h = swatch_size_mm
    total_w = w * len(thicknesses)
    total_h = h

    all_verts = []
    all_faces = []
    face_offset = 0

    for i, t in enumerate(thicknesses):
        x0 = i * w
        x1 = x0 + w
        thick = base_thickness_mm + t

        # Simple box: top face at z=thick, bottom at z=0
        verts = np.array([
            [x0, 0, 0],      # 0: bottom-left-back
            [x1, 0, 0],      # 1: bottom-right-back
            [x1, h, 0],      # 2: bottom-right-front
            [x0, h, 0],      # 3: bottom-left-front
            [x0, 0, thick],  # 4: top-left-back
            [x1, 0, thick],  # 5: top-right-back
            [x1, h, thick],  # 6: top-right-front
            [x0, h, thick],  # 7: top-left-front
        ], dtype=np.float32)

        faces = np.array([
            [0, 1, 2], [0, 2, 3],  # bottom
            [4, 6, 5], [4, 7, 6],  # top
            [0, 4, 5], [0, 5, 1],  # back
            [2, 6, 7], [2, 7, 3],  # front
            [0, 3, 7], [0, 7, 4],  # left
            [1, 5, 6], [1, 6, 2],  # right
        ], dtype=np.int32)

        all_verts.append(verts)
        all_faces.append(faces + face_offset)
        face_offset += len(verts)

    verts = np.vstack(all_verts)
    faces = np.vstack(all_faces)

    _write_binary_stl(output_path, verts, faces)

    # Print info
    print(json.dumps({
        "output": output_path,
        "thicknesses_tested": thicknesses,
        "swatch_size_mm": list(swatch_size_mm),
        "base_thickness_mm": base_thickness_mm,
        "instructions": (
            "Print this swatch at 100% infill. Hold against a bright light. "
            "For each step, measure the luminance (0=dark, 255=bright). "
            "Then run: --calculate --measurements '[[thickness_mm, luminance], ...]'"
        ),
    }, indent=2))


# ── Step 2: Calculate TD from measurements ──

def calculate_td(measurements, filament_name="Unknown"):
    """Calculate Transmission Distance from thickness/luminance measurements.

    Uses Beer-Lambert law: luminance = L0 * 10^(-thickness / TD)
    Linearizing: log10(luminance) = log10(L0) - thickness / TD
    Fit via linear regression: y = a + b*x where b = -1/TD, so TD = -1/b

    Args:
        measurements: List of (thickness_mm, luminance) tuples.
            luminance: 0-255 scale measured through the filament.
        filament_name: Name for the output report.

    Returns:
        dict with keys: td_mm, r_squared, confidence, luminance_0
    """
    if len(measurements) < 3:
        return {"error": "Need at least 3 measurements for reliable regression"}

    x = np.array([m[0] for m in measurements], dtype=np.float64)
    y = np.array([max(m[1], 1.0) for m in measurements], dtype=np.float64)  # avoid log(0)

    log_y = np.log10(y)

    # Linear regression: log_y = a + b*x
    n = len(x)
    x_mean = x.mean()
    y_mean = log_y.mean()
    s_xx = np.sum((x - x_mean) ** 2)
    s_xy = np.sum((x - x_mean) * (log_y - y_mean))

    b = s_xy / s_xx
    a = y_mean - b * x_mean

    # TD = -1/b (since b should be negative)
    td = -1.0 / b if b < 0 else float("inf")

    # R² goodness of fit
    y_pred = a + b * x
    ss_res = np.sum((log_y - y_pred) ** 2)
    ss_tot = np.sum((log_y - y_mean) ** 2)
    r_sq = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Luminance at zero thickness (backlight reference)
    lum_0 = 10.0 ** a

    # Confidence
    if r_sq > 0.95:
        confidence = "High"
    elif r_sq > 0.85:
        confidence = "Medium"
    elif r_sq > 0.70:
        confidence = "Low"
    else:
        confidence = "Very Low"

    # Validate
    if td > 15.0:
        confidence = "Very Low"
        td = min(td, 15.0)

    return {
        "filament_name": filament_name,
        "td_mm": round(td, 2),
        "r_squared": round(r_sq, 4),
        "confidence": confidence,
        "luminance_backlight": round(lum_0, 1),
        "measurements": [[round(x[i], 2), round(y[i], 1)] for i in range(n)],
        "formula": f"L = {lum_0:.1f} × 10^(-thickness / {td:.2f})",
        "usage_hint": (
            f'Add to --filaments JSON: '
            f'{{"color":"#??????","td":{td:.2f},"name":"{filament_name}"}}'
        ),
    }


# ── Utility ──

def _write_binary_stl(path, verts, faces):
    """Write binary STL file."""
    verts = verts.astype(np.float32)
    faces = faces.astype(np.int32)

    with open(path, 'wb') as f:
        f.write(b'\x00' * 80)
        f.write(struct.pack('<I', len(faces)))
        for tri in faces:
            v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
            e1 = v1 - v0
            e2 = v2 - v0
            n = np.cross(e1, e2)
            n = n / (np.linalg.norm(n) + 1e-10)
            f.write(struct.pack('<3f', *n))
            f.write(struct.pack('<3f', *v0))
            f.write(struct.pack('<3f', *v1))
            f.write(struct.pack('<3f', *v2))
            f.write(struct.pack('<H', 0))


# ── CLI ──

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calibrate filament Transmission Distance (TD) for multi-color 3D printing")
    parser.add_argument("--generate", action="store_true",
                        help="Generate calibration swatch STL")
    parser.add_argument("--output", type=str, default="calibrate_swatch.stl",
                        help="Output path for generated swatch (default: calibrate_swatch.stl)")
    parser.add_argument("--thicknesses", type=str, default=None,
                        help="Comma-separated thicknesses in mm (default: 0.3,0.6,1.0,1.5,2.0,3.0)")
    parser.add_argument("--swatch-size", type=str, default="20,20",
                        help="Width,height of each step in mm (default: 20,20)")
    parser.add_argument("--base-thickness", type=float, default=0.6,
                        help="Base/backing thickness in mm (default: 0.6)")

    parser.add_argument("--calculate", action="store_true",
                        help="Calculate TD from measurements")
    parser.add_argument("--measurements", type=str, default=None,
                        help='JSON array of [thickness_mm, luminance] pairs')
    parser.add_argument("--name", type=str, default="Unknown",
                        help="Filament name for the output report")

    args = parser.parse_args()

    if args.generate:
        thicknesses = None
        if args.thicknesses:
            thicknesses = [float(t.strip()) for t in args.thicknesses.split(",")]
        swatch = tuple(int(s.strip()) for s in args.swatch_size.split(","))
        generate_calibration_swatch(args.output, thicknesses, swatch,
                                    args.base_thickness)
    elif args.calculate:
        if not args.measurements:
            print(json.dumps({"error": "--measurements is required with --calculate"}))
            sys.exit(1)
        try:
            measurements = json.loads(args.measurements)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid --measurements JSON: {e}"}))
            sys.exit(1)
        result = calculate_td(measurements, args.name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        parser.print_help()
