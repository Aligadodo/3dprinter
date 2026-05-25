/** Three.js 3D preview renderer for multi-color relief/lithophane.
 *
 * Renders a height-field mesh with vertex colors computed by the Web Worker.
 * Supports orbit controls, front/back toggle, and flat color overlay.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { rgbToLab, cie76, luminance } from './color-utils.js';

let scene, camera, renderer, controls;
let mesh, wireframe;
let animationId;
let _viewMode = 'front'; // 'front' | 'back' | 'both'

/** Initialize the Three.js renderer into a container element. */
export function initPreview(container, canvasWidth, canvasHeight) {
    if (renderer) cleanup();

    // Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a2e);

    // Camera
    camera = new THREE.PerspectiveCamera(45, canvasWidth / canvasHeight, 0.1, 1000);
    camera.position.set(0, -1.5, 1.2);
    camera.lookAt(0, 0, 0.3);

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(canvasWidth, canvasHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    // Controls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0.3);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 0.3;
    controls.maxDistance = 5;
    controls.maxPolarAngle = Math.PI * 0.7;
    controls.update();

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x404060, 0.6);
    scene.add(ambientLight);

    const frontLight = new THREE.DirectionalLight(0xffffff, 0.8);
    frontLight.position.set(0, -2, 3);
    scene.add(frontLight);

    const backLight = new THREE.DirectionalLight(0x8888cc, 0.3);
    backLight.position.set(0, 2, -1);
    scene.add(backLight);

    const sideLight = new THREE.DirectionalLight(0xffffff, 0.3);
    sideLight.position.set(2, 0, 1);
    scene.add(sideLight);

    // Grid helper
    const grid = new THREE.GridHelper(0.5, 10, 0x444466, 0x222244);
    grid.position.z = -0.01;
    scene.add(grid);

    // Start render loop
    function animate() {
        animationId = requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();
}

/** Update the 3D mesh with new height map and color data. */
export function updateMesh(heightMap, colorMap, width, height,
                           physWidthMm, physHeightMm, baseThicknessMm, maxDepthMm) {
    if (mesh) scene.remove(mesh);
    if (wireframe) scene.remove(wireframe);

    var w = width, h = height;
    var dx = physWidthMm / 1000 / Math.max(w - 1, 1);
    var dy = physHeightMm / 1000 / Math.max(h - 1, 1);
    var totalThicknessM = (baseThicknessMm + (maxDepthMm || 0)) / 1000;

    var geometry = new THREE.PlaneGeometry(
        physWidthMm / 1000, physHeightMm / 1000, w - 1, h - 1);
    geometry.rotateX(-Math.PI / 2);

    const positions = geometry.attributes.position;
    const colors = new Float32Array(positions.count * 3);

    // Displace Z and assign vertex colors
    for (let i = 0; i < positions.count; i++) {
        // Map vertex index back to pixel
        const row = Math.floor(i / w);
        const col = i % w;

        if (row < h && col < w) {
            const z = baseThicknessMm / 1000 + heightMap[row * w + col] / 1000;
            positions.setZ(i, z);

            const ci = (row * w + col) * 3;
            colors[i * 3]     = colorMap[ci]     / 255;
            colors[i * 3 + 1] = colorMap[ci + 1] / 255;
            colors[i * 3 + 2] = colorMap[ci + 2] / 255;
        }
    }

    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
        vertexColors: true,
        roughness: 0.5,
        metalness: 0.05,
        side: _viewMode === 'back' ? THREE.BackSide : THREE.FrontSide,
    });

    mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);

    // Optional wireframe overlay
    const wireMat = new THREE.MeshBasicMaterial({
        color: 0x000000,
        wireframe: true,
        transparent: true,
        opacity: 0.03,
    });
    wireframe = new THREE.Mesh(geometry, wireMat);
    scene.add(wireframe);

    // Fit camera to mesh including Z thickness
    var maxDim = Math.max(physWidthMm, physHeightMm, (maxDepthMm || 0)) / 1000;
    var dist = Math.max(maxDim * 1.8, 0.3);
    camera.position.set(dist * 0.6, -dist * 0.9, dist * 0.7 + totalThicknessM);
    controls.target.set(0, 0, totalThicknessM * 0.5);
    controls.update();
}

/** Toggle between front-lit and back-lit view. */
export function setViewMode(mode) {
    _viewMode = mode;
    if (mesh) {
        if (mode === 'back') {
            mesh.material.side = THREE.BackSide;
            camera.position.set(
                camera.position.x,
                -camera.position.y,
                camera.position.z);
        } else {
            mesh.material.side = THREE.FrontSide;
        }
        mesh.material.needsUpdate = true;
    }
}

/** Cleanup renderer resources. */
export function cleanup() {
    if (animationId) cancelAnimationFrame(animationId);
    if (renderer) {
        renderer.dispose();
        renderer.domElement.remove();
        renderer = null;
    }
    if (controls) { controls.dispose(); controls = null; }
    if (mesh) { mesh.geometry.dispose(); mesh.material.dispose(); mesh = null; }
    if (wireframe) { wireframe.geometry.dispose(); wireframe.material.dispose(); wireframe = null; }
    scene = null; camera = null;
}

/** Resize canvas to match container. */
export function resize(width, height) {
    if (!renderer) return;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
}

/** Get the canvas element for screenshots. */
export function getCanvas() {
    return renderer ? renderer.domElement : null;
}
