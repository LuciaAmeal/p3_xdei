import * as THREE from '../vendor/three/three.module.js';
import { OrbitControls } from '../vendor/three/examples/jsm/controls/OrbitControls.js';

const DEFAULT_CENTER = {
  lat: 43.3623,
  lon: -8.4115,
};

const BUILDING_PALETTE = [0x96a5b8, 0x7f93a9, 0x9aa2ad, 0xb1b7c1, 0x7e8ca1];
const VEHICLE_POLL_INTERVAL_MS = 2000;
const VEHICLE_TRANSITION_MS = 1850;
const VEHICLE_WORLD_SCALE = 0.03;
const VEHICLE_BODY_LENGTH = 4.8;
const VEHICLE_BODY_WIDTH = 2.2;
const VEHICLE_BODY_HEIGHT = 1.2;
const VEHICLE_SNAP_DISTANCE = 180;
const ROUTE_FALLBACK_PALETTE = [
  '#0b74de',
  '#ff8a00',
  '#1f9d55',
  '#e11d48',
  '#7c3aed',
  '#0f766e',
  '#b45309',
  '#2563eb',
];

function initScene3D() {
  if (window.__XDEI_SCENE3D_INITIALIZED) {
    return;
  }

  const container = document.getElementById('scene-root') || document.getElementById('map');
  if (!container) {
    return;
  }

  window.__XDEI_SCENE3D_INITIALIZED = true;

  const statusEl = document.getElementById('map-status');
  const timelineStatusEl = document.getElementById('timeline-status');
  const timelineLabelEl = document.getElementById('timeline-label');
  const timelineCountEl = document.getElementById('timeline-count');
  const timelineRangeEl = document.getElementById('timeline-slider');
  const timelinePlayEl = document.getElementById('timeline-play');
  const timelineLiveEl = document.getElementById('timeline-live');
  const dateFromEl = document.getElementById('date-from');
  const dateToEl = document.getElementById('date-to');
  const dateFilterApplyEl = document.getElementById('date-filter-apply');
  const replaySpeedEl = document.getElementById('replay-speed');
  const vehicleFiltersToggleEl = document.getElementById('vehicle-filters-toggle');
  const vehicleFiltersListEl = document.getElementById('vehicle-filters-list');
  const detailPanelEl = document.getElementById('detail-panel');
  const detailPanelBodyEl = document.getElementById('detail-panel-body');
  const detailPanelTitleEl = detailPanelEl ? detailPanelEl.querySelector('.detail-panel__title') : null;

  const supportsWebGL = (() => {
    try {
      const testCanvas = document.createElement('canvas');
      return Boolean(testCanvas.getContext('webgl2') || testCanvas.getContext('webgl'));
    } catch (error) {
      return false;
    }
  })();

  if (!supportsWebGL) {
    if (statusEl) {
      statusEl.textContent = 'Este navegador no soporta WebGL.';
    }
    if (detailPanelEl && detailPanelBodyEl) {
      detailPanelEl.classList.add('detail-panel--empty');
      if (detailPanelTitleEl) {
        detailPanelTitleEl.textContent = 'WebGL no disponible';
      }
      detailPanelBodyEl.innerHTML = '<p class="detail-panel__empty-state">La escena Three.js necesita soporte WebGL para renderizar el terreno y los edificios.</p>';
    }
    return;
  }

  if (statusEl) {
    statusEl.textContent = 'Preparando escena 3D…';
  }

  if (timelineStatusEl) {
    timelineStatusEl.textContent = 'Terreno, edificios y vehículos en carga';
  }

  if (timelineLabelEl) {
    timelineLabelEl.textContent = 'Vehículos coloreados por ruta';
  }

  if (timelineCountEl) {
    timelineCountEl.textContent = 'Interpolación y heading activos';
  }

  [timelineRangeEl, timelinePlayEl, timelineLiveEl, dateFromEl, dateToEl, dateFilterApplyEl, replaySpeedEl, vehicleFiltersToggleEl].forEach((element) => {
    if (element) {
      element.disabled = true;
    }
  });

  if (vehicleFiltersListEl) {
    vehicleFiltersListEl.innerHTML = '<p class="detail-panel__empty-state" style="margin:0;">Vista base 3D sin filtros activos.</p>';
    vehicleFiltersListEl.style.display = 'block';
  }

  if (detailPanelEl && detailPanelBodyEl) {
    detailPanelEl.classList.add('detail-panel--empty');
    if (detailPanelTitleEl) {
      detailPanelTitleEl.textContent = 'Escena 3D activa';
    }
    detailPanelBodyEl.innerHTML = '<p class="detail-panel__empty-state">Terreno texturado, edificios con LOD sencillo y vehículos 3D coloreados por ruta. Cada vehículo se interpola entre actualizaciones y gira según su heading.</p>';
  }

  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: false,
    powerPreference: 'low-power',
    preserveDrawingBuffer: false,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setSize(container.clientWidth, container.clientHeight, false);
  renderer.setClearColor(0x0b1220, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.domElement.style.display = 'block';
  renderer.domElement.style.width = '100%';
  renderer.domElement.style.height = '100%';
  renderer.domElement.style.willChange = 'transform';
  container.replaceChildren(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b1220);
  scene.fog = new THREE.Fog(0x0b1220, 180, 820);

  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 2000);
  camera.position.set(160, 130, 170);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.enablePan = false;
  controls.minDistance = 90;
  controls.maxDistance = 520;
  controls.minPolarAngle = Math.PI * 0.2;
  controls.maxPolarAngle = Math.PI * 0.48;
  controls.target.set(0, 18, 0);
  controls.update();

  const ambientLight = new THREE.AmbientLight(0xcdd7e8, 1.2);
  scene.add(ambientLight);

  const hemiLight = new THREE.HemisphereLight(0x8ec8ff, 0x1a2a33, 1.15);
  scene.add(hemiLight);

  const sunLight = new THREE.DirectionalLight(0xfff1d0, 2.1);
  sunLight.position.set(170, 260, 120);
  scene.add(sunLight);

  const cityCenter = DEFAULT_CENTER;
  const groundSize = 320;
  const groundTexture = createGroundTexture();
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(groundSize, groundSize, 1, 1),
    new THREE.MeshStandardMaterial({
      map: groundTexture,
      roughness: 1,
      metalness: 0,
      color: 0xc7cfb3,
    })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = false;
  scene.add(ground);

  const grid = new THREE.GridHelper(groundSize, 24, 0x507095, 0x223345);
  grid.position.y = 0.1;
  grid.material.transparent = true;
  grid.material.opacity = 0.28;
  scene.add(grid);

  addPerimeterRoad(scene, groundSize);
  addBuildingClusters(scene, groundSize);
  addLandmarks(scene);

  const routeLookup = new Map();
  const vehicleStates = new Map();
  let vehicleManagerUnsubscribe = null;

  function setSceneStatus(message) {
    if (statusEl) {
      statusEl.textContent = message;
    }
  }

  function normalizeColor(value, fallback) {
    if (typeof value !== 'string') {
      return fallback;
    }

    const trimmed = value.trim();
    const hex = trimmed.startsWith('#') ? trimmed.slice(1) : trimmed;
    if (/^[0-9a-fA-F]{6}$/.test(hex)) {
      return `#${hex.toLowerCase()}`;
    }

    return fallback;
  }

  function hashColor(seed) {
    const source = String(seed || 'vehicle');
    let hash = 0;

    for (let index = 0; index < source.length; index += 1) {
      hash = (hash << 5) - hash + source.charCodeAt(index);
      hash |= 0;
    }

    const paletteIndex = Math.abs(hash) % ROUTE_FALLBACK_PALETTE.length;
    return ROUTE_FALLBACK_PALETTE[paletteIndex];
  }

  function getRouteColor(route, vehicle) {
    const fallback = hashColor(vehicle.tripId || vehicle.vehicleId || vehicle.id || 'vehicle');
    return normalizeColor(route && route.routeColor, fallback);
  }

  function buildRouteLookup(routes) {
    routeLookup.clear();

    (Array.isArray(routes) ? routes : []).forEach((route) => {
      if (!route || !route.id) {
        return;
      }

      routeLookup.set(route.id, route);
      (Array.isArray(route.tripIds) ? route.tripIds : []).forEach((tripId) => {
        if (tripId) {
          routeLookup.set(tripId, route);
        }
      });
    });
  }

  function resolveWorldPosition(position) {
    if (!Array.isArray(position) || position.length < 2) {
      return null;
    }

    const lon = Number(position[0]);
    const lat = Number(position[1]);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      return null;
    }

    const metersPerDegreeLat = 110540;
    const metersPerDegreeLon = 111320 * Math.cos(THREE.MathUtils.degToRad(DEFAULT_CENTER.lat));
    const x = (lon - DEFAULT_CENTER.lon) * metersPerDegreeLon * VEHICLE_WORLD_SCALE;
    const z = -((lat - DEFAULT_CENTER.lat) * metersPerDegreeLat * VEHICLE_WORLD_SCALE);
    return new THREE.Vector3(x, 1.55, z);
  }

  function resolveVehicleHeading(vehicle) {
    const heading = Number(vehicle && vehicle.heading);
    return Number.isFinite(heading) ? heading : 0;
  }

  function normalizeHeadingDegrees(value) {
    if (!Number.isFinite(value)) {
      return 0;
    }

    let heading = value % 360;
    if (heading < -180) {
      heading += 360;
    }
    if (heading > 180) {
      heading -= 360;
    }
    return heading;
  }

  function shortestAngleDegrees(from, to) {
    return normalizeHeadingDegrees(to - from);
  }

  function lerpAngleDegrees(from, to, alpha) {
    return from + shortestAngleDegrees(from, to) * alpha;
  }

  function createVehicleMaterial(color) {
    return new THREE.MeshStandardMaterial({
      color,
      roughness: 0.42,
      metalness: 0.12,
      flatShading: false,
    });
  }

  const vehicleMaterialCache = new Map();

  function getVehicleMaterial(color) {
    const normalizedColor = normalizeColor(color, '#0b74de');
    if (vehicleMaterialCache.has(normalizedColor)) {
      return vehicleMaterialCache.get(normalizedColor);
    }

    const material = createVehicleMaterial(normalizedColor);
    vehicleMaterialCache.set(normalizedColor, material);
    return material;
  }

  function createVehicleMesh(color) {
    const group = new THREE.Group();
    group.name = 'vehicle-mesh';

    const bodyMaterial = getVehicleMaterial(color);
    const windowMaterial = new THREE.MeshStandardMaterial({
      color: 0x192432,
      roughness: 0.28,
      metalness: 0.05,
      transparent: true,
      opacity: 0.94,
    });
    const accentMaterial = new THREE.MeshStandardMaterial({
      color: 0xe8eef7,
      roughness: 0.65,
      metalness: 0.1,
    });
    const wheelMaterial = new THREE.MeshStandardMaterial({
      color: 0x101820,
      roughness: 0.92,
      metalness: 0,
    });

    const body = new THREE.Mesh(
      new THREE.BoxGeometry(VEHICLE_BODY_WIDTH, VEHICLE_BODY_HEIGHT, VEHICLE_BODY_LENGTH, 1, 1, 2),
      bodyMaterial
    );
    body.position.y = 0.9;
    group.add(body);

    const roof = new THREE.Mesh(
      new THREE.BoxGeometry(VEHICLE_BODY_WIDTH * 0.84, VEHICLE_BODY_HEIGHT * 0.55, VEHICLE_BODY_LENGTH * 0.68),
      bodyMaterial
    );
    roof.position.set(0, 1.5, -0.12);
    group.add(roof);

    const windshield = new THREE.Mesh(
      new THREE.BoxGeometry(VEHICLE_BODY_WIDTH * 0.68, VEHICLE_BODY_HEIGHT * 0.34, 0.46),
      windowMaterial
    );
    windshield.position.set(0, 1.28, -VEHICLE_BODY_LENGTH * 0.41);
    group.add(windshield);

    const frontPanel = new THREE.Mesh(
      new THREE.BoxGeometry(VEHICLE_BODY_WIDTH * 0.84, VEHICLE_BODY_HEIGHT * 0.24, 0.18),
      accentMaterial
    );
    frontPanel.position.set(0, 0.74, -VEHICLE_BODY_LENGTH * 0.52);
    group.add(frontPanel);

    const wheelGeometry = new THREE.CylinderGeometry(0.32, 0.32, 0.22, 10);
    const wheelOffsets = [
      [-0.9, 0.36, -1.45],
      [0.9, 0.36, -1.45],
      [-0.9, 0.36, 1.45],
      [0.9, 0.36, 1.45],
    ];

    wheelOffsets.forEach(([x, y, z]) => {
      const wheel = new THREE.Mesh(wheelGeometry, wheelMaterial);
      wheel.rotation.z = Math.PI / 2;
      wheel.position.set(x, y, z);
      group.add(wheel);
    });

    const headlightGeometry = new THREE.BoxGeometry(0.16, 0.12, 0.08);
    const headlightOffsets = [-0.55, 0.55];
    headlightOffsets.forEach((x) => {
      const light = new THREE.Mesh(headlightGeometry, accentMaterial);
      light.position.set(x, 0.85, -VEHICLE_BODY_LENGTH * 0.54);
      group.add(light);
    });

    group.userData.bodyMeshes = [body, roof];
    return group;
  }

  function getVehicleState(vehicleId) {
    return vehicleStates.get(vehicleId) || null;
  }

  function sampleStatePosition(state, now) {
    if (!state) {
      return new THREE.Vector3();
    }

    const duration = Math.max(1, state.transitionDuration || 1);
    const alpha = Math.min(1, Math.max(0, (now - state.transitionStart) / duration));
    return new THREE.Vector3().copy(state.fromPosition).lerp(state.toPosition, alpha);
  }

  function sampleStateHeading(state, now) {
    if (!state) {
      return 0;
    }

    const duration = Math.max(1, state.transitionDuration || 1);
    const alpha = Math.min(1, Math.max(0, (now - state.transitionStart) / duration));
    return lerpAngleDegrees(state.fromHeading, state.toHeading, alpha);
  }

  function upsertVehicle(vehicle, now) {
    if (!vehicle || !vehicle.vehicleId) {
      return;
    }

    const vehicleId = String(vehicle.vehicleId);
    const route = routeLookup.get(vehicle.tripId) || routeLookup.get(vehicle.routeId) || null;
    const targetColor = getRouteColor(route, vehicle);
    const targetPosition = resolveWorldPosition(vehicle.currentPosition);
    const targetHeading = normalizeHeadingDegrees(resolveVehicleHeading(vehicle));

    if (!targetPosition) {
      return;
    }

    const existing = getVehicleState(vehicleId);
    if (!existing) {
      const mesh = createVehicleMesh(targetColor);
      mesh.position.copy(targetPosition);
      mesh.rotation.y = THREE.MathUtils.degToRad(targetHeading);
      scene.add(mesh);

      vehicleStates.set(vehicleId, {
        id: vehicleId,
        mesh,
        color: targetColor,
        routeId: route && route.id ? route.id : null,
        fromPosition: targetPosition.clone(),
        toPosition: targetPosition.clone(),
        fromHeading: targetHeading,
        toHeading: targetHeading,
        transitionStart: now,
        transitionDuration: 1,
      });
      return;
    }

    const currentDisplayPosition = sampleStatePosition(existing, now);
    const currentDisplayHeading = sampleStateHeading(existing, now);
    const distance = currentDisplayPosition.distanceTo(targetPosition);
    const transitionDuration = distance > VEHICLE_SNAP_DISTANCE ? 1 : VEHICLE_TRANSITION_MS;

    existing.routeId = route && route.id ? route.id : null;
    existing.color = targetColor;
    if (Array.isArray(existing.mesh.userData.bodyMeshes)) {
      existing.mesh.userData.bodyMeshes.forEach((mesh) => {
        mesh.material = getVehicleMaterial(targetColor);
      });
    }
    existing.fromPosition = currentDisplayPosition;
    existing.toPosition = targetPosition.clone();
    existing.fromHeading = currentDisplayHeading;
    existing.toHeading = targetHeading;
    existing.transitionStart = now;
    existing.transitionDuration = transitionDuration;
  }

  function removeMissingVehicles(seenVehicleIds) {
    vehicleStates.forEach((state, vehicleId) => {
      if (seenVehicleIds.has(vehicleId)) {
        return;
      }

      scene.remove(state.mesh);
      vehicleStates.delete(vehicleId);
    });
  }

  function syncVehicles(vehicles, sourceLabel) {
    const now = performance.now();
    const seenVehicleIds = new Set();

    (Array.isArray(vehicles) ? vehicles : []).forEach((vehicle) => {
      if (!vehicle || !vehicle.vehicleId) {
        return;
      }

      seenVehicleIds.add(String(vehicle.vehicleId));
      upsertVehicle(vehicle, now);
    });

    removeMissingVehicles(seenVehicleIds);

    if (timelineStatusEl) {
      const count = vehicleStates.size;
      const suffix = sourceLabel ? ` · ${sourceLabel}` : '';
      timelineStatusEl.textContent = `${count} vehículos 3D activos${suffix}`;
    }

    if (timelineCountEl) {
      timelineCountEl.textContent = `${vehicleStates.size} meshes animados`;
    }
  }

  function refreshVehicleMeshes(now) {
    vehicleStates.forEach((state) => {
      const nextPosition = sampleStatePosition(state, now);
      const nextHeading = sampleStateHeading(state, now);

      state.mesh.position.copy(nextPosition);
      state.mesh.rotation.y = THREE.MathUtils.degToRad(nextHeading);
    });
  }

  function getVehicleManager() {
    if (typeof window.VehicleManager === 'undefined' || !window.VehicleManager) {
      return null;
    }

    return window.VehicleManager;
  }

  function connectVehicleManager() {
    const manager = getVehicleManager();
    if (!manager || typeof manager.subscribe !== 'function') {
      if (timelineStatusEl) {
        timelineStatusEl.textContent = 'Cliente de datos no disponible';
      }
      return;
    }

    if (typeof vehicleManagerUnsubscribe === 'function') {
      vehicleManagerUnsubscribe();
    }

    vehicleManagerUnsubscribe = manager.subscribe(function (vehicles, meta) {
      const sourceLabel = meta && meta.source ? meta.source : 'live';
      syncVehicles(vehicles, sourceLabel);
    });
  }

  function loadSceneData() {
    if (!window.MapApiClient || typeof window.MapApiClient.loadMapData !== 'function') {
      buildRouteLookup([]);
      connectVehicleManager();
      return;
    }

    setSceneStatus('Cargando rutas y vehículos…');
    window.MapApiClient.loadMapData()
      .then((data) => {
        const routes = data && Array.isArray(data.routes) ? data.routes : [];
        const vehicles = data && Array.isArray(data.vehicles) ? data.vehicles : [];

        buildRouteLookup(routes);
        const manager = getVehicleManager();
        if (manager && typeof manager.setVehicles === 'function') {
          manager.setVehicles(vehicles, { source: 'bootstrap' });
        } else {
          syncVehicles(vehicles, 'bootstrap');
        }

        connectVehicleManager();

        if (statusEl) {
          statusEl.textContent = 'Escena 3D lista · vehículos coloreados por ruta, interpolados y orientados por heading';
        }
      })
      .catch((error) => {
        console.warn('Unable to load map data for 3D scene:', error);
        buildRouteLookup([]);
        syncVehicles([], 'fallback');
        connectVehicleManager();
      });
  }

  const resize = () => {
    const width = Math.max(1, container.clientWidth);
    const height = Math.max(1, container.clientHeight);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
  };

  const resizeObserver = 'ResizeObserver' in window ? new ResizeObserver(resize) : null;
  if (resizeObserver) {
    resizeObserver.observe(container);
  }

  window.addEventListener('resize', resize);

  const helpText = `Escena centrada en ${cityCenter.lat.toFixed(4)}, ${cityCenter.lon.toFixed(4)}`;
  if (timelineStatusEl) {
    timelineStatusEl.textContent = helpText;
  }

  let animationFrameId = null;
  let pulse = 0;

  function renderFrame() {
    animationFrameId = window.requestAnimationFrame(renderFrame);
    pulse += 0.0035;
    controls.update();
    refreshVehicleMeshes(performance.now());
    sunLight.position.x = 170 + Math.sin(pulse * 0.8) * 10;
    sunLight.position.z = 120 + Math.cos(pulse * 0.6) * 10;
    renderer.render(scene, camera);
  }

  function cleanup() {
    if (animationFrameId !== null) {
      window.cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
    if (typeof vehicleManagerUnsubscribe === 'function') {
      vehicleManagerUnsubscribe();
      vehicleManagerUnsubscribe = null;
    }
    vehicleStates.forEach((state) => {
      scene.remove(state.mesh);
    });
    vehicleStates.clear();
    if (resizeObserver) {
      resizeObserver.disconnect();
    }
    window.removeEventListener('resize', resize);
  }

  window.addEventListener('beforeunload', cleanup, { once: true });

  if (statusEl) {
    statusEl.textContent = 'Escena 3D lista · cargando vehículos coloreados por ruta';
  }

  loadSceneData();
  renderFrame();
}

function createGroundTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 1024;
  const context = canvas.getContext('2d');

  if (!context) {
    return new THREE.Texture(canvas);
  }

  const baseGradient = context.createLinearGradient(0, 0, 0, canvas.height);
  baseGradient.addColorStop(0, '#334735');
  baseGradient.addColorStop(0.45, '#425c42');
  baseGradient.addColorStop(1, '#2b3c2f');
  context.fillStyle = baseGradient;
  context.fillRect(0, 0, canvas.width, canvas.height);

  const cellSize = 64;
  for (let y = 0; y < canvas.height; y += cellSize) {
    for (let x = 0; x < canvas.width; x += cellSize) {
      const lightness = 0.03 + ((x + y) % (cellSize * 2)) / (cellSize * 48);
      context.fillStyle = `rgba(255, 255, 255, ${lightness.toFixed(3)})`;
      context.fillRect(x, y, cellSize, cellSize);
    }
  }

  context.strokeStyle = 'rgba(255, 255, 255, 0.08)';
  context.lineWidth = 2;
  for (let index = 0; index <= canvas.width; index += cellSize) {
    context.beginPath();
    context.moveTo(index, 0);
    context.lineTo(index, canvas.height);
    context.stroke();

    context.beginPath();
    context.moveTo(0, index);
    context.lineTo(canvas.width, index);
    context.stroke();
  }

  for (let index = 0; index < 360; index += 1) {
    const x = Math.random() * canvas.width;
    const y = Math.random() * canvas.height;
    const radius = 0.6 + Math.random() * 2.4;
    context.fillStyle = Math.random() > 0.5 ? 'rgba(28, 44, 35, 0.22)' : 'rgba(255, 255, 255, 0.05)';
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fill();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(8, 8);
  texture.anisotropy = 4;
  texture.needsUpdate = true;
  return texture;
}

function addPerimeterRoad(scene, groundSize) {
  const roadMaterial = new THREE.MeshStandardMaterial({
    color: 0x1d2835,
    roughness: 1,
    metalness: 0,
  });

  const roadMesh = new THREE.Mesh(new THREE.PlaneGeometry(groundSize * 0.92, 10), roadMaterial);
  roadMesh.rotation.x = -Math.PI / 2;
  roadMesh.position.set(0, 0.12, 0);
  scene.add(roadMesh);

  const roadRing = new THREE.Mesh(new THREE.RingGeometry(groundSize * 0.38, groundSize * 0.42, 56), roadMaterial);
  roadRing.rotation.x = -Math.PI / 2;
  roadRing.position.y = 0.12;
  scene.add(roadRing);
}

function addBuildingClusters(scene, groundSize) {
  const layout = createBuildingLayout(groundSize);
  layout.forEach((spec) => {
    const building = new THREE.LOD();

    building.addLevel(createDetailedBuilding(spec), 0);
    building.addLevel(createMidBuilding(spec), 120);
    building.addLevel(createSimpleBuilding(spec), 220);

    building.position.set(spec.x, 0, spec.z);
    building.userData = spec;
    scene.add(building);
  });
}

function createBuildingLayout(groundSize) {
  const buildings = [];
  const rng = seededRandom(20);
  const rows = 6;
  const cols = 7;
  const spacingX = groundSize / (cols + 1);
  const spacingZ = groundSize / (rows + 1);

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const x = (col - (cols - 1) / 2) * spacingX + (rng() - 0.5) * 10;
      const z = (row - (rows - 1) / 2) * spacingZ + (rng() - 0.5) * 10;
      const width = 11 + rng() * 8;
      const depth = 10 + rng() * 8;
      const height = 12 + rng() * 42;
      const paletteIndex = Math.floor(rng() * BUILDING_PALETTE.length);

      buildings.push({
        x,
        z,
        width,
        depth,
        height,
        color: BUILDING_PALETTE[paletteIndex],
        roofColor: paletteIndex % 2 === 0 ? 0x627488 : 0x4d5c70,
      });
    }
  }

  const landmarks = [
    { x: -54, z: -48, width: 18, depth: 18, height: 78, color: 0x95a7bb, roofColor: 0x5f6d80 },
    { x: 48, z: -36, width: 22, depth: 16, height: 64, color: 0x7f95ab, roofColor: 0x556579 },
    { x: -22, z: 56, width: 20, depth: 20, height: 72, color: 0xaab4c0, roofColor: 0x6d7b8e },
  ];

  landmarks.forEach((landmark) => buildings.push(landmark));

  return buildings;
}

function createDetailedBuilding(spec) {
  const group = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(spec.width, spec.height, spec.depth, 2, 3, 2),
    new THREE.MeshStandardMaterial({
      color: spec.color,
      roughness: 0.92,
      metalness: 0.02,
      flatShading: true,
    })
  );
  body.position.y = spec.height / 2;
  group.add(body);

  const capHeight = Math.max(1.2, spec.height * 0.08);
  const cap = new THREE.Mesh(
    new THREE.BoxGeometry(spec.width * 0.88, capHeight, spec.depth * 0.88),
    new THREE.MeshStandardMaterial({
      color: spec.roofColor,
      roughness: 0.82,
      metalness: 0.05,
    })
  );
  cap.position.y = spec.height + capHeight * 0.5 - 0.2;
  group.add(cap);

  if (spec.height > 36) {
    const antenna = new THREE.Mesh(
      new THREE.CylinderGeometry(0.25, 0.5, 8, 6),
      new THREE.MeshStandardMaterial({ color: 0xd0d7df, roughness: 0.7 })
    );
    antenna.position.set(0, spec.height + capHeight + 4, 0);
    group.add(antenna);
  }

  group.position.y = 0;
  return group;
}

function createMidBuilding(spec) {
  const geometry = new THREE.BoxGeometry(spec.width * 0.98, spec.height, spec.depth * 0.98, 1, 2, 1);
  const material = new THREE.MeshStandardMaterial({
    color: spec.color,
    roughness: 0.94,
    metalness: 0.01,
    flatShading: true,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.y = spec.height / 2;
  return mesh;
}

function createSimpleBuilding(spec) {
  const geometry = new THREE.BoxGeometry(spec.width * 0.94, spec.height * 0.98, spec.depth * 0.94);
  const material = new THREE.MeshStandardMaterial({
    color: spec.color,
    roughness: 0.98,
    metalness: 0,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.y = spec.height * 0.49;
  return mesh;
}

function addLandmarks(scene) {
  const accent = new THREE.Mesh(
    new THREE.TorusGeometry(26, 1.2, 8, 48),
    new THREE.MeshStandardMaterial({ color: 0xffcf5a, roughness: 0.7, metalness: 0.1 })
  );
  accent.rotation.x = Math.PI / 2;
  accent.position.set(0, 1.6, 0);
  scene.add(accent);
}

function seededRandom(seed) {
  let state = seed % 2147483647;
  if (state <= 0) {
    state += 2147483646;
  }

  return function random() {
    state = (state * 16807) % 2147483647;
    return (state - 1) / 2147483646;
  };
}

if (typeof window !== 'undefined') {
  window.initScene3D = initScene3D;
  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', initScene3D, { once: true });
  } else {
    initScene3D();
  }
}