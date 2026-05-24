/** TD database — static JS version of scripts/multi_color/td_database.py.
 *
 * Maps (brand, color_name) → TD (mm).
 * TD = thickness at which ~90% of light is blocked.
 * Lower TD = more opaque, Higher TD = more translucent.
 */

const KNOWN_TD = {
    // ── Bambu Lab PLA Basic ──
    "bambu|black": 0.6,
    "bambu|charcoal": 0.8,
    "bambu|dark brown": 0.9,
    "bambu|brown": 1.2,
    "bambu|dark blue": 1.0,
    "bambu|blue": 2.8,
    "bambu|blue gray": 3.1,
    "bambu|gray": 1.5,
    "bambu|light gray": 3.0,
    "bambu|silver": 2.5,
    "bambu|dark green": 1.0,
    "bambu|green": 2.5,
    "bambu|lime green": 4.5,
    "bambu|mint green": 4.0,
    "bambu|dark red": 1.0,
    "bambu|red": 3.5,
    "bambu|crimson": 2.5,
    "bambu|orange": 4.0,
    "bambu|yellow": 5.5,
    "bambu|gold": 3.5,
    "bambu|purple": 2.5,
    "bambu|magenta": 3.0,
    "bambu|pink": 4.0,
    "bambu|cyan": 4.5,
    "bambu|white": 4.4,
    "bambu|jade white": 5.0,
    "bambu|ivory white": 5.5,
    "bambu|beige": 4.0,
    "bambu|natural": 6.0,

    // ── Bambu Lab PLA Matte ──
    "bambu matte|black": 0.4,
    "bambu matte|charcoal": 0.5,
    "bambu matte|dark brown": 0.8,
    "bambu matte|dark blue": 0.8,
    "bambu matte|blue": 2.5,
    "bambu matte|gray": 1.2,
    "bambu matte|light gray": 2.8,
    "bambu matte|dark green": 0.8,
    "bambu matte|green": 2.2,
    "bambu matte|dark red": 1.0,
    "bambu matte|red": 3.0,
    "bambu matte|orange": 3.5,
    "bambu matte|yellow": 5.0,
    "bambu matte|purple": 2.2,
    "bambu matte|magenta": 2.8,
    "bambu matte|pink": 3.5,
    "bambu matte|white": 3.5,
    "bambu matte|ivory white": 4.5,
    "bambu matte|beige": 3.5,

    // ── Polymaker PolyTerra PLA ──
    "polymaker|black": 0.5,
    "polymaker|charcoal": 0.8,
    "polymaker|dark brown": 1.0,
    "polymaker|brown": 1.5,
    "polymaker|navy blue": 1.0,
    "polymaker|blue": 3.0,
    "polymaker|gray": 1.5,
    "polymaker|light gray": 3.5,
    "polymaker|dark green": 1.0,
    "polymaker|green": 2.8,
    "polymaker|lime green": 5.0,
    "polymaker|dark red": 1.2,
    "polymaker|red": 3.5,
    "polymaker|orange": 4.5,
    "polymaker|yellow": 6.0,
    "polymaker|purple": 2.8,
    "polymaker|pink": 4.5,
    "polymaker|cyan": 5.0,
    "polymaker|white": 4.5,
    "polymaker|beige": 4.0,

    // ── Sunlu PLA ──
    "sunlu|black": 0.7,
    "sunlu|gray": 1.8,
    "sunlu|blue": 3.2,
    "sunlu|red": 3.5,
    "sunlu|green": 3.0,
    "sunlu|yellow": 5.5,
    "sunlu|orange": 4.5,
    "sunlu|white": 4.5,

    // ── eSun PLA+ ──
    "esun|black": 0.5,
    "esun|gray": 1.5,
    "esun|dark blue": 1.0,
    "esun|blue": 3.0,
    "esun|red": 3.5,
    "esun|green": 2.8,
    "esun|yellow": 5.0,
    "esun|orange": 4.0,
    "esun|white": 4.0,
    "esun|natural": 5.5,

    // ── Generic / Unknown PLA ──
    "generic|black": 0.6,
    "generic|dark gray": 1.0,
    "generic|gray": 1.8,
    "generic|light gray": 3.0,
    "generic|dark blue": 1.0,
    "generic|blue": 3.0,
    "generic|cyan": 4.5,
    "generic|dark green": 1.0,
    "generic|green": 2.8,
    "generic|dark red": 1.2,
    "generic|red": 3.5,
    "generic|orange": 4.2,
    "generic|yellow": 5.0,
    "generic|purple": 2.8,
    "generic|magenta": 3.2,
    "generic|pink": 4.0,
    "generic|brown": 1.5,
    "generic|white": 4.5,
    "generic|natural": 5.5,
};

/** Approximate sRGB values for named colors (used for palette→filament matching). */
const COLOR_RGB = {
    "black":       [15, 15, 15],
    "charcoal":    [54, 69, 79],
    "dark brown":  [60, 30, 20],
    "brown":       [120, 70, 40],
    "navy blue":   [20, 20, 80],
    "dark blue":   [20, 40, 130],
    "blue":        [30, 80, 200],
    "blue gray":   [100, 120, 150],
    "light blue":  [150, 190, 230],
    "gray":        [128, 128, 128],
    "light gray":  [190, 190, 190],
    "silver":      [192, 192, 196],
    "dark green":  [20, 80, 30],
    "green":       [30, 150, 60],
    "lime green":  [50, 205, 50],
    "mint green":  [150, 230, 180],
    "dark red":    [130, 20, 20],
    "red":         [210, 40, 40],
    "crimson":     [180, 20, 50],
    "orange":      [240, 130, 30],
    "yellow":      [245, 220, 30],
    "gold":        [212, 175, 55],
    "purple":      [130, 50, 180],
    "magenta":     [210, 30, 140],
    "pink":        [240, 150, 180],
    "cyan":        [30, 200, 210],
    "white":       [245, 245, 245],
    "jade white":  [235, 238, 225],
    "ivory white": [245, 240, 225],
    "beige":       [225, 210, 180],
    "natural":     [220, 210, 190],
};

const COLOR_NAMES = Object.keys(COLOR_RGB);

/** Fuzzy-lookup TD for a filament name/color description. */
function lookupTD(name) {
    const s = name.toLowerCase().trim();
    // Try exact match first
    for (const [key, td] of Object.entries(KNOWN_TD)) {
        const [brandPart, colorPart] = key.split("|");
        if (s.includes(brandPart) && s.includes(colorPart)) return td;
    }
    // Try color-only match (generic)
    for (const colorName of COLOR_NAMES) {
        if (s.includes(colorName)) {
            const key = `generic|${colorName}`;
            if (KNOWN_TD[key] !== undefined) return KNOWN_TD[key];
        }
    }
    return 4.0; // conservative default
}

/** Find closest known filaments for a list of RGB colors. */
function findClosestFilaments(rgbList) {
    // Build reference entries
    const refs = [];
    for (const [key, td] of Object.entries(KNOWN_TD)) {
        const [brand, colorName] = key.split("|");
        const rgb = COLOR_RGB[colorName];
        if (rgb) {
            refs.push({ brand, colorName, td, rgb });
        }
    }

    const results = [];
    const seenNames = new Set();

    for (const targetRgb of rgbList) {
        const targetLab = rgbToLab(targetRgb[0] / 255, targetRgb[1] / 255, targetRgb[2] / 255);
        let bestRef = null, bestDE = Infinity;

        for (const ref of refs) {
            const refLab = rgbToLab(ref.rgb[0] / 255, ref.rgb[1] / 255, ref.rgb[2] / 255);
            const de = cie76(targetLab, refLab);
            if (de < bestDE) { bestDE = de; bestRef = ref; }
        }

        if (bestRef && !seenNames.has(bestRef.colorName)) {
            seenNames.add(bestRef.colorName);
            const hex = "#" + bestRef.rgb.map(c => c.toString(16).padStart(2, "0")).join("");
            results.push({
                color: hex,
                name: bestRef.brand + " " + bestRef.colorName,
                td: bestRef.td,
                r: bestRef.rgb[0],
                g: bestRef.rgb[1],
                b: bestRef.rgb[2],
            });
        }
    }

    // Sort dark→light (luminance ascending)
    results.sort((a, b) => {
        const lumA = 0.2126 * a.r + 0.7152 * a.g + 0.0722 * a.b;
        const lumB = 0.2126 * b.r + 0.7152 * b.g + 0.0722 * b.b;
        return lumA - lumB;
    });

    return results;
}

// Import color utilities (worker will use importScripts or self-contained)
// These are duplicated here so the worker is self-contained

/** sRGB → CIE Lab (D65 illuminant). */
function rgbToLab(r, g, b) {
    // sRGB linearize
    const lin = (c) => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    const rl = lin(r), gl = lin(g), bl = lin(b);

    // sRGB → XYZ (D65)
    const x = 0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl;
    const y = 0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl;
    const z = 0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl;

    // XYZ → Lab
    const xn = 0.95047, yn = 1.0, zn = 1.08883;
    const delta = 6 / 29;
    const delta3 = delta ** 3;
    const f = (t) => t > delta3 ? Math.cbrt(t) : t / (3 * delta * delta) + 4 / 29;

    const fy = f(y / yn);
    const L = 116 * fy - 16;
    const a = 500 * (f(x / xn) - fy);
    const bLab = 200 * (fy - f(z / zn));

    return [L, a, bLab];
}

/** CIE76 color difference (Euclidean distance in Lab space). */
function cie76(lab1, lab2) {
    const dL = lab1[0] - lab2[0];
    const da = lab1[1] - lab2[1];
    const db = lab1[2] - lab2[2];
    return Math.sqrt(dL * dL + da * da + db * db);
}

/** Simple K-means clustering for dominant color extraction. */
function kmeansColors(pixels, k, maxIter = 10) {
    const n = pixels.length;
    if (n === 0) return [];

    // Initialize centroids with random pixels
    const centroids = [];
    const used = new Set();
    while (centroids.length < k) {
        const idx = Math.floor(Math.random() * n);
        if (!used.has(idx)) {
            used.add(idx);
            centroids.push([pixels[idx][0], pixels[idx][1], pixels[idx][2]]);
        }
    }

    const labels = new Int32Array(n);

    for (let iter = 0; iter < maxIter; iter++) {
        // Assign labels
        let changed = 0;
        for (let i = 0; i < n; i++) {
            const p = pixels[i];
            let bestC = 0, bestD = Infinity;
            for (let c = 0; c < k; c++) {
                const dr = p[0] - centroids[c][0];
                const dg = p[1] - centroids[c][1];
                const db = p[2] - centroids[c][2];
                const d = dr * dr + dg * dg + db * db;
                if (d < bestD) { bestD = d; bestC = c; }
            }
            if (labels[i] !== bestC) changed++;
            labels[i] = bestC;
        }

        // Update centroids
        const sums = Array.from({ length: k }, () => [0, 0, 0]);
        const counts = new Int32Array(k);
        for (let i = 0; i < n; i++) {
            const c = labels[i];
            sums[c][0] += pixels[i][0];
            sums[c][1] += pixels[i][1];
            sums[c][2] += pixels[i][2];
            counts[c]++;
        }
        for (let c = 0; c < k; c++) {
            if (counts[c] > 0) {
                centroids[c][0] = sums[c][0] / counts[c];
                centroids[c][1] = sums[c][1] / counts[c];
                centroids[c][2] = sums[c][2] / counts[c];
            }
        }

        if (changed === 0) break;
    }

    return centroids.map(c => [Math.round(c[0]), Math.round(c[1]), Math.round(c[2])]);
}

/** Hex color string → {r, g, b} 0-255. */
function hexToRgb(hex) {
    const h = hex.replace("#", "");
    return {
        r: parseInt(h.substring(0, 2), 16),
        g: parseInt(h.substring(2, 4), 16),
        b: parseInt(h.substring(4, 6), 16),
    };
}
