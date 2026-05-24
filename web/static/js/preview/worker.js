/** Web Worker: Beer-Lambert multi-color preview simulation.
 *
 * Post incoming message:
 *   { imageData: ImageData, numColors: N, layerHeight: mm, maxDepth: mm,
 *     baseThickness: mm, ditherStrength: 0-1, lithophane: bool }
 *
 * Post outgoing message:
 *   { heightMap: Float32Array(H*W), colorMap: Uint8Array(H*W*3),
 *     filaments: [...], swaps: [...], log: [...] }
 *
 * ── Inlined from td-db.js + color-utils.js for self-containment ──
 */

// ═══════════════════════════════════════════════════════════════
// TD database
// ═══════════════════════════════════════════════════════════════

const KNOWN_TD = {
    "bambu|black":0.6,"bambu|charcoal":0.8,"bambu|dark brown":0.9,"bambu|brown":1.2,
    "bambu|dark blue":1.0,"bambu|blue":2.8,"bambu|blue gray":3.1,"bambu|gray":1.5,
    "bambu|light gray":3.0,"bambu|silver":2.5,"bambu|dark green":1.0,"bambu|green":2.5,
    "bambu|lime green":4.5,"bambu|mint green":4.0,"bambu|dark red":1.0,"bambu|red":3.5,
    "bambu|crimson":2.5,"bambu|orange":4.0,"bambu|yellow":5.5,"bambu|gold":3.5,
    "bambu|purple":2.5,"bambu|magenta":3.0,"bambu|pink":4.0,"bambu|cyan":4.5,
    "bambu|white":4.4,"bambu|jade white":5.0,"bambu|ivory white":5.5,"bambu|beige":4.0,
    "bambu|natural":6.0,
    "bambu matte|black":0.4,"bambu matte|charcoal":0.5,"bambu matte|dark brown":0.8,
    "bambu matte|dark blue":0.8,"bambu matte|blue":2.5,"bambu matte|gray":1.2,
    "bambu matte|light gray":2.8,"bambu matte|dark green":0.8,"bambu matte|green":2.2,
    "bambu matte|dark red":1.0,"bambu matte|red":3.0,"bambu matte|orange":3.5,
    "bambu matte|yellow":5.0,"bambu matte|purple":2.2,"bambu matte|magenta":2.8,
    "bambu matte|pink":3.5,"bambu matte|white":3.5,"bambu matte|ivory white":4.5,
    "bambu matte|beige":3.5,
    "polymaker|black":0.5,"polymaker|charcoal":0.8,"polymaker|navy blue":1.0,
    "polymaker|blue":3.0,"polymaker|gray":1.5,"polymaker|light gray":3.5,
    "polymaker|dark green":1.0,"polymaker|green":2.8,"polymaker|lime green":5.0,
    "polymaker|red":3.5,"polymaker|orange":4.5,"polymaker|yellow":6.0,
    "polymaker|purple":2.8,"polymaker|pink":4.5,"polymaker|cyan":5.0,
    "polymaker|white":4.5,"polymaker|beige":4.0,
    "sunlu|black":0.7,"sunlu|gray":1.8,"sunlu|blue":3.2,"sunlu|red":3.5,
    "sunlu|green":3.0,"sunlu|yellow":5.5,"sunlu|orange":4.5,"sunlu|white":4.5,
    "esun|black":0.5,"esun|gray":1.5,"esun|dark blue":1.0,"esun|blue":3.0,
    "esun|red":3.5,"esun|green":2.8,"esun|yellow":5.0,"esun|orange":4.0,
    "esun|white":4.0,"esun|natural":5.5,
    "generic|black":0.6,"generic|dark gray":1.0,"generic|gray":1.8,"generic|light gray":3.0,
    "generic|dark blue":1.0,"generic|blue":3.0,"generic|cyan":4.5,"generic|dark green":1.0,
    "generic|green":2.8,"generic|dark red":1.2,"generic|red":3.5,"generic|orange":4.2,
    "generic|yellow":5.0,"generic|purple":2.8,"generic|magenta":3.2,"generic|pink":4.0,
    "generic|brown":1.5,"generic|white":4.5,"generic|natural":5.5,
};

const COLOR_RGB = {
    "black":[15,15,15],"charcoal":[54,69,79],"dark brown":[60,30,20],"brown":[120,70,40],
    "navy blue":[20,20,80],"dark blue":[20,40,130],"blue":[30,80,200],"blue gray":[100,120,150],
    "light blue":[150,190,230],"gray":[128,128,128],"light gray":[190,190,190],"silver":[192,192,196],
    "dark green":[20,80,30],"green":[30,150,60],"lime green":[50,205,50],"mint green":[150,230,180],
    "dark red":[130,20,20],"red":[210,40,40],"crimson":[180,20,50],"orange":[240,130,30],
    "yellow":[245,220,30],"gold":[212,175,55],"purple":[130,50,180],"magenta":[210,30,140],
    "pink":[240,150,180],"cyan":[30,200,210],"white":[245,245,245],"jade white":[235,238,225],
    "ivory white":[245,240,225],"beige":[225,210,180],"natural":[220,210,190],
};

// ═══════════════════════════════════════════════════════════════
// Color utilities (self-contained)
// ═══════════════════════════════════════════════════════════════

function rgbToLab(r, g, b) {
    const lin = (c) => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    const rl = lin(r), gl = lin(g), bl = lin(b);
    const x = 0.4124564*rl + 0.3575761*gl + 0.1804375*bl;
    const y = 0.2126729*rl + 0.7151522*gl + 0.0721750*bl;
    const z = 0.0193339*rl + 0.1191920*gl + 0.9503041*bl;
    const xn=0.95047, yn=1.0, zn=1.08883;
    const d=6/29, d3=d*d*d;
    const f=(t)=>t>d3?Math.cbrt(t):t/(3*d*d)+4/29;
    const fy=f(y/yn);
    return [116*fy-16, 500*(f(x/xn)-fy), 200*(fy-f(z/zn))];
}

function cie76(lab1, lab2) {
    const dL=lab1[0]-lab2[0], da=lab1[1]-lab2[1], db=lab1[2]-lab2[2];
    return Math.sqrt(dL*dL+da*da+db*db);
}

// ═══════════════════════════════════════════════════════════════
// K-means
// ═══════════════════════════════════════════════════════════════

function kmeansColors(pixels, k, maxIter) {
    maxIter = maxIter || 10;
    var n = pixels.length;
    if (n === 0) return [];
    var cents = [];
    var used = {};
    while (cents.length < k) {
        var idx = Math.floor(Math.random() * n);
        if (!used[idx]) { used[idx]=true; cents.push([pixels[idx][0],pixels[idx][1],pixels[idx][2]]); }
    }
    var labels = new Int32Array(n);
    for (var iter=0; iter<maxIter; iter++) {
        var changed = 0;
        for (var i=0; i<n; i++) {
            var p=pixels[i], bestC=0, bestD=Infinity;
            for (var c=0; c<k; c++) {
                var dr=p[0]-cents[c][0], dg=p[1]-cents[c][1], db=p[2]-cents[c][2];
                var d=dr*dr+dg*dg+db*db;
                if (d<bestD) { bestD=d; bestC=c; }
            }
            if (labels[i]!==bestC) changed++;
            labels[i]=bestC;
        }
        var sums=[], counts=new Int32Array(k);
        for (var c=0; c<k; c++) sums.push([0,0,0]);
        for (var i=0; i<n; i++) {
            var cl=labels[i];
            sums[cl][0]+=pixels[i][0]; sums[cl][1]+=pixels[i][1]; sums[cl][2]+=pixels[i][2];
            counts[cl]++;
        }
        for (var c=0; c<k; c++) {
            if (counts[c]>0) { cents[c][0]=sums[c][0]/counts[c]; cents[c][1]=sums[c][1]/counts[c]; cents[c][2]=sums[c][2]/counts[c]; }
        }
        if (changed===0) break;
    }
    return cents.map(function(c) { return [Math.round(c[0]), Math.round(c[1]), Math.round(c[2])]; });
}

// ═══════════════════════════════════════════════════════════════
// Filament matching
// ═══════════════════════════════════════════════════════════════

function findClosestFilaments(rgbList) {
    var refs = [];
    for (var key in KNOWN_TD) {
        var parts = key.split("|");
        var brand = parts[0], colorName = parts[1];
        var rgb = COLOR_RGB[colorName];
        if (rgb) refs.push({ brand:brand, colorName:colorName, td:KNOWN_TD[key], rgb:rgb });
    }

    var results = [], seenNames = {};
    for (var i=0; i<rgbList.length; i++) {
        var tr=rgbList[i];
        var targetLab = rgbToLab(tr[0]/255, tr[1]/255, tr[2]/255);
        var bestRef=null, bestDE=Infinity;
        for (var j=0; j<refs.length; j++) {
            var ref=refs[j];
            var refLab=rgbToLab(ref.rgb[0]/255, ref.rgb[1]/255, ref.rgb[2]/255);
            var de=cie76(targetLab, refLab);
            if (de<bestDE) { bestDE=de; bestRef=ref; }
        }
        if (bestRef && !seenNames[bestRef.colorName]) {
            seenNames[bestRef.colorName]=true;
            var hex="#"+bestRef.rgb.map(function(c){return c.toString(16).padStart(2,"0");}).join("");
            results.push({ color:hex, name:bestRef.brand+" "+bestRef.colorName, td:bestRef.td,
                r:bestRef.rgb[0], g:bestRef.rgb[1], b:bestRef.rgb[2] });
        }
    }
    results.sort(function(a,b) {
        return (0.2126*a.r+0.7152*a.g+0.0722*a.b) - (0.2126*b.r+0.7152*b.g+0.0722*b.b);
    });
    return results;
}

// ═══════════════════════════════════════════════════════════════
// Beer-Lambert simulation
// ═══════════════════════════════════════════════════════════════

function beerLambertTransmission(thickness, td) {
    return Math.pow(10, -thickness / Math.max(td, 0.01));
}

function beerLambertBlend(layerStack, layerHeight) {
    var r=1, g=1, b=1;
    for (var i=0; i<layerStack.length; i++) {
        var filament=layerStack[i][0], thickness=layerStack[i][1];
        var nSteps=Math.max(1, Math.round(thickness/layerHeight));
        var stepT=thickness/nSteps;
        var fr=filament.r/255, fg=filament.g/255, fb=filament.b/255;
        for (var s=0; s<nSteps; s++) {
            var tr=beerLambertTransmission(stepT, filament.td);
            r = r*tr + fr*(1-tr);
            g = g*tr + fg*(1-tr);
            b = b*tr + fb*(1-tr);
        }
    }
    return [r, g, b];
}

function generateVirtualSwatches(orderedFilaments, layerAssignments, layerHeight) {
    var swatches = [];
    var currentZ = 0;
    for (var a=0; a<layerAssignments.length; a++) {
        var assignment = layerAssignments[a];
        var filIdx = assignment.filamentIndex;
        var thickness = assignment.thickness;
        var nSteps = Math.max(1, Math.round(thickness / layerHeight));
        var step = thickness / nSteps;
        for (var s=0; s<nSteps; s++) {
            var sampleZ = currentZ + (s+0.5)*step;
            var stack = buildStackUpTo(orderedFilaments, layerAssignments, sampleZ, layerHeight);
            var blended = beerLambertBlend(stack, layerHeight);
            swatches.push({ z_mm: Math.round(sampleZ*1e4)/1e4, rgb: blended, topFilamentIndex: filIdx });
        }
        currentZ += thickness;
    }
    return swatches;
}

function buildStackUpTo(filaments, assignments, targetZ, layerHeight) {
    var stack = [];
    var currentZ = 0;
    for (var a=0; a<assignments.length; a++) {
        var assignment = assignments[a];
        var thickness = assignment.thickness;
        var nextZ = currentZ + thickness;
        if (nextZ <= targetZ + 1e-6) {
            stack.push([filaments[assignment.filamentIndex], thickness]);
        } else if (currentZ < targetZ) {
            var partial = targetZ - currentZ;
            stack.push([filaments[assignment.filamentIndex], partial]);
            break;
        } else break;
        currentZ = nextZ;
    }
    return stack;
}

// ═══════════════════════════════════════════════════════════════
// Height mapping
// ═══════════════════════════════════════════════════════════════

function mapColorsToHeight(imageRGB, swatches, maxHeight, layerHeight, ditherStrength, lithophane) {
    var H=imageRGB.length, W=imageRGB[0].length;
    var nPixels = H*W;
    var pixels = new Array(nPixels);
    for (var y=0; y<H; y++) {
        for (var x=0; x<W; x++) {
            pixels[y*W+x] = [imageRGB[y][x][0]/255, imageRGB[y][x][1]/255, imageRGB[y][x][2]/255];
        }
    }

    // Precompute swatch Labs
    var swatchLabs = swatches.map(function(s) { return rgbToLab(s.rgb[0], s.rgb[1], s.rgb[2]); });
    var swatchHeights = swatches.map(function(s) { return s.z_mm; });

    // Batch match pixels to swatches
    var heightIndices = new Int32Array(nPixels);
    var BATCH=20000;
    for (var start=0; start<nPixels; start+=BATCH) {
        var end=Math.min(start+BATCH, nPixels);
        for (var i=start; i<end; i++) {
            var pLab=rgbToLab(pixels[i][0], pixels[i][1], pixels[i][2]);
            var bestJ=0, bestD=Infinity;
            for (var j=0; j<swatchLabs.length; j++) {
                var d=cie76(pLab, swatchLabs[j]);
                if (d<bestD) { bestD=d; bestJ=j; }
            }
            heightIndices[i]=bestJ;
        }
    }

    var heightMap = new Float32Array(nPixels);
    for (var i=0; i<nPixels; i++) {
        heightMap[i] = swatchHeights[heightIndices[i]];
    }

    // Floyd-Steinberg dithering
    if (ditherStrength > 0.001) {
        heightMap = floydSteinbergHeight(heightMap, heightIndices, swatches, H, W, ditherStrength);
    }

    // Invert for relief mode
    if (!lithophane) {
        for (var i=0; i<nPixels; i++) {
            heightMap[i] = maxHeight - heightMap[i];
        }
    }

    // Clamp
    for (var i=0; i<nPixels; i++) {
        if (heightMap[i] < 0) heightMap[i] = 0;
        if (heightMap[i] > maxHeight) heightMap[i] = maxHeight;
    }

    return { heightMap: heightMap, heightIndices: heightIndices };
}

function floydSteinbergHeight(heightMap, indices, swatches, H, W, strength) {
    var hm = new Float64Array(heightMap);
    var kernel = [[0,1,7/16],[1,-1,3/16],[1,0,5/16],[1,1,1/16]];

    for (var y=0; y<H; y++) {
        for (var x=0; x<W; x++) {
            var idx = y*W + x;
            var currentZ = hm[idx];
            var currentIdx = indices[idx];
            var swatchZ = swatches[currentIdx].z_mm;

            var quantized = currentZ; // stay at current
            var zError = (currentZ - quantized) * strength;

            if (Math.abs(zError) < 1e-10) continue;
            hm[idx] = quantized;

            var currentTop = swatches[currentIdx].topFilamentIndex;
            for (var k=0; k<4; k++) {
                var ny=y+kernel[k][0], nx=x+kernel[k][1];
                if (ny>=0 && ny<H && nx>=0 && nx<W) {
                    var nIdx=ny*W+nx;
                    if (swatches[indices[nIdx]].topFilamentIndex === currentTop) {
                        hm[nIdx] += zError * kernel[k][2];
                    }
                }
            }
        }
    }
    return new Float32Array(hm);
}

// ═══════════════════════════════════════════════════════════════
// Layer plan builder (simplified for preview — luminance order only)
// ═══════════════════════════════════════════════════════════════

var FOUNDATION_FACTOR = 1.3;
var DELTA_E_JND = 2.3;
var OPACITY_CONVERGED = 0.85;

function buildLayerPlan(filaments, layerHeight, maxThickness) {
    if (filaments.length === 0) return { assignments: [], totalHeight: 0 };
    if (filaments.length === 1) {
        var t = Math.min(filaments[0].td * FOUNDATION_FACTOR, maxThickness);
        t = Math.max(1, Math.round(t/layerHeight))*layerHeight;
        return { assignments: [{filamentIndex:0, thickness:t}], totalHeight: t };
    }

    var assignments = [];
    var totalH = 0;

    // Foundation for darkest (bottom)
    var foundation = filaments[0].td * FOUNDATION_FACTOR;
    foundation = Math.min(foundation, maxThickness * 0.4);
    var nL = Math.max(1, Math.round(foundation/layerHeight));
    foundation = nL * layerHeight;
    assignments.push({ filamentIndex: 0, thickness: foundation });
    totalH = foundation;

    // Transition zones
    for (var i=1; i<filaments.length; i++) {
        var budget = maxThickness - totalH;
        if (budget <= layerHeight) break;
        var transT = computeTransitionZone(filaments, i, layerHeight, budget);
        if (transT > 0) {
            assignments.push({ filamentIndex: i, thickness: transT });
            totalH += transT;
        }
    }

    // Top gets remaining budget
    if (totalH < maxThickness && filaments.length > 0) {
        var remaining = maxThickness - totalH;
        var nL2 = Math.round(remaining/layerHeight);
        if (nL2 > 0) {
            var lastIdx = assignments[assignments.length-1].filamentIndex;
            if (lastIdx === filaments.length-1) {
                assignments[assignments.length-1].thickness += nL2 * layerHeight;
            } else {
                assignments.push({ filamentIndex: filaments.length-1, thickness: nL2 * layerHeight });
            }
            totalH += nL2 * layerHeight;
        }
    }

    return { assignments: assignments, totalHeight: totalH };
}

function computeTransitionZone(filaments, topIdx, layerHeight, maxBudget) {
    var topFil = filaments[topIdx];
    var topRgb = [topFil.r/255, topFil.g/255, topFil.b/255];
    var topLab = rgbToLab(topRgb[0], topRgb[1], topRgb[2]);
    var maxLayers = Math.floor(maxBudget / layerHeight);

    for (var n=1; n<=maxLayers; n++) {
        var thickness = n * layerHeight;
        // Simulate: below stack (approx) + n layers of top
        var stack = [];
        for (var i=0; i<topIdx; i++) {
            stack.push([filaments[i], filaments[i].td * 0.5]);
        }
        stack.push([topFil, thickness]);
        var blended = beerLambertBlend(stack, layerHeight);
        var blendedLab = rgbToLab(blended[0], blended[1], blended[2]);
        var de = cie76(topLab, blendedLab);

        var opacity = 1.0;
        for (var i=0; i<stack.length; i++) {
            opacity *= beerLambertTransmission(stack[i][1], Math.max(stack[i][0].td, 0.01));
        }
        opacity = 1 - opacity;

        if (de < DELTA_E_JND || opacity > OPACITY_CONVERGED) return thickness;
    }
    return maxLayers * layerHeight;
}

// ═══════════════════════════════════════════════════════════════
// Main entry point
// ═══════════════════════════════════════════════════════════════

self.onmessage = function(e) {
    var data = e.data;
    var imgData = data.imageData;
    var numColors = data.numColors || 4;
    var layerHeight = data.layerHeight || 0.08;
    var maxDepth = data.maxDepth || 3.0;
    var baseThickness = data.baseThickness || 0.6;
    var ditherStrength = data.ditherStrength || 0.8;
    var lithophane = data.lithophane || false;

    var W = imgData.width, H = imgData.height;
    var pixels = imgData.data; // Uint8ClampedArray RGBA

    // ── Extract RGB array ──
    var imageRGB = new Array(H);
    for (var y=0; y<H; y++) {
        imageRGB[y] = new Array(W);
        for (var x=0; x<W; x++) {
            var i = (y*W + x)*4;
            imageRGB[y][x] = [pixels[i], pixels[i+1], pixels[i+2]];
        }
    }

    // ── Subsample for K-means (every 4th pixel) ──
    var samplePixels = [];
    for (var y=0; y<H; y+=2) {
        for (var x=0; x<W; x+=2) {
            samplePixels.push(imageRGB[y][x]);
        }
    }

    // ── Extract dominant colors → match filaments ──
    var dominantRgb = kmeansColors(samplePixels, numColors);
    var filaments = findClosestFilaments(dominantRgb);

    if (filaments.length === 0) {
        filaments = [
            { color:"#000000", name:"Black PLA", td:0.6, r:15, g:15, b:15 },
            { color:"#FFFFFF", name:"White PLA", td:4.4, r:245, g:245, b:245 },
        ];
    }

    // ── Build layer plan ──
    var plan = buildLayerPlan(filaments, layerHeight, maxDepth);

    // ── Generate virtual swatches ──
    var swatches = generateVirtualSwatches(filaments, plan.assignments, layerHeight);

    // ── Map pixels to heights ──
    var result = mapColorsToHeight(imageRGB, swatches, maxDepth, layerHeight, ditherStrength, lithophane);

    // ── Compute per-pixel blended color (from swatch lookup) ──
    var colorMap = new Uint8Array(H*W*3);
    for (var i=0; i<H*W; i++) {
        var swIdx = result.heightIndices[i];
        var rgb = swatches[swIdx].rgb;
        colorMap[i*3]   = Math.min(255, Math.max(0, Math.round(rgb[0]*255)));
        colorMap[i*3+1] = Math.min(255, Math.max(0, Math.round(rgb[1]*255)));
        colorMap[i*3+2] = Math.min(255, Math.max(0, Math.round(rgb[2]*255)));
    }

    // ── Build swap list ──
    var swaps = [];
    var currentZ = 0;
    for (var a=0; a<plan.assignments.length; a++) {
        var fi = plan.assignments[a].filamentIndex;
        if (a===0 || fi!==plan.assignments[a-1].filamentIndex) {
            swaps.push({
                z_mm: Math.round(currentZ*1e3)/1e3,
                layer_number: Math.floor(currentZ/layerHeight)+1,
                filament_index: fi,
                filament_name: filaments[fi].name,
                color: filaments[fi].color,
            });
        }
        currentZ += plan.assignments[a].thickness;
    }

    // ── Post result ──
    // Transfer the buffers for zero-copy
    var heightMap = result.heightMap;
    self.postMessage({
        heightMap: heightMap.buffer,
        colorMap: colorMap.buffer,
        width: W,
        height: H,
        filaments: filaments,
        swaps: swaps,
        totalHeightMm: plan.totalHeight + baseThickness,
        log: [
            "Colors: " + filaments.length + " filaments",
            "Layer height: " + layerHeight + " mm",
            "Total blend height: " + plan.totalHeight.toFixed(2) + " mm",
            "Swatches: " + swatches.length,
            "Pixels: " + W + "x" + H,
        ],
    }, [heightMap.buffer, colorMap.buffer]);
};
