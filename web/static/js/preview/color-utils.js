/** Color utilities for preview — CIE Lab, CIE76, CIE2000.
 *
 * Exported for use in the main thread (renderer, UI).
 * The worker bundles its own copy of the core functions for self-containment.
 */

/** sRGB → CIE Lab (D65 illuminant, 2° observer). */
export function rgbToLab(r, g, b) {
    const lin = (c) => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    const rl = lin(r), gl = lin(g), bl = lin(b);

    const x = 0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl;
    const y = 0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl;
    const z = 0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl;

    const xn = 0.95047, yn = 1.0, zn = 1.08883;
    const d = 6 / 29, d3 = d * d * d;
    const f = (t) => t > d3 ? Math.cbrt(t) : t / (3 * d * d) + 4 / 29;

    const fy = f(y / yn);
    return [
        116 * fy - 16,
        500 * (f(x / xn) - fy),
        200 * (fy - f(z / zn)),
    ];
}

/** CIE76 — Euclidean distance in Lab. Fast, sufficient for preview. */
export function cie76(lab1, lab2) {
    const dL = lab1[0] - lab2[0];
    const da = lab1[1] - lab2[1];
    const db = lab1[2] - lab2[2];
    return Math.sqrt(dL * dL + da * da + db * db);
}

/** CIEDE2000 — perceptually accurate color difference.
 *
 * Used only for final filament-to-palette matching accuracy.
 * Reference: Sharma, Wu, & Dalal (2005).
 */
export function deltaE2000(lab1, lab2) {
    const [L1, a1, b1] = lab1;
    const [L2, a2, b2] = lab2;

    const LBar = (L1 + L2) / 2;
    const C1 = Math.sqrt(a1 * a1 + b1 * b1);
    const C2 = Math.sqrt(a2 * a2 + b2 * b2);
    const CBar = (C1 + C2) / 2;

    const CBar7 = CBar ** 7;
    const G = 0.5 * (1 - Math.sqrt(CBar7 / (CBar7 + 25 ** 7)));

    const a1p = a1 * (1 + G);
    const a2p = a2 * (1 + G);

    const C1p = Math.sqrt(a1p * a1p + b1 * b1);
    const C2p = Math.sqrt(a2p * a2p + b2 * b2);
    const CbarP = (C1p + C2p) / 2;

    let h1p = (Math.atan2(b1, a1p) * 180) / Math.PI;
    if (h1p < 0) h1p += 360;
    let h2p = (Math.atan2(b2, a2p) * 180) / Math.PI;
    if (h2p < 0) h2p += 360;

    let HbarP;
    if (Math.abs(h1p - h2p) <= 180) {
        HbarP = (h1p + h2p) / 2;
    } else {
        HbarP = (h1p + h2p + 360) / 2;
    }

    const T = 1 - 0.17 * Math.cos((HbarP - 30) * Math.PI / 180)
        + 0.24 * Math.cos((2 * HbarP) * Math.PI / 180)
        + 0.32 * Math.cos((3 * HbarP + 6) * Math.PI / 180)
        - 0.20 * Math.cos((4 * HbarP - 63) * Math.PI / 180);

    let dh = Math.abs(h1p - h2p);
    if (dh > 180) dh = 360 - dh;
    const deltaHp = 2 * Math.sqrt(C1p * C2p) * Math.sin((dh / 2) * Math.PI / 180);

    const deltaLp = L2 - L1;
    const deltaCp = C2p - C1p;

    const SL = 1 + (0.015 * (LBar - 50) ** 2) / Math.sqrt(20 + (LBar - 50) ** 2);
    const SC = 1 + 0.045 * CbarP;
    const SH = 1 + 0.015 * CbarP * T;

    const dTheta = 30 * Math.exp(-(((HbarP - 275) / 25) ** 2));
    const RC = 2 * Math.sqrt(CbarP ** 7 / (CbarP ** 7 + 25 ** 7));
    const RT = -RC * Math.sin((2 * dTheta) * Math.PI / 180);

    const t1 = deltaLp / SL;
    const t2 = deltaCp / SC;
    const t3 = deltaHp / SH;

    return Math.sqrt(t1 * t1 + t2 * t2 + t3 * t3 + RT * t2 * t3);
}

/** Hex → normalized RGB [0,1]. */
export function hexToRgb(hex) {
    const h = hex.replace("#", "");
    return [
        parseInt(h.substring(0, 2), 16) / 255,
        parseInt(h.substring(2, 4), 16) / 255,
        parseInt(h.substring(4, 6), 16) / 255,
    ];
}

/** Normalized RGB [0,1] → hex string. */
export function rgbToHex(r, g, b) {
    const clamp = (v) => Math.max(0, Math.min(255, Math.round(v * 255)));
    return "#" + [clamp(r), clamp(g), clamp(b)]
        .map(c => c.toString(16).padStart(2, "0")).join("");
}

/** Perceived luminance (ITU-R BT.709). */
export function luminance(r, g, b) {
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
