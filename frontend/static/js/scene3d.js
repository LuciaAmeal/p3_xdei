import * as THREE from '../vendor/three/three.module.js';
import { OrbitControls } from '../vendor/three/examples/jsm/controls/OrbitControls.js';

const DEFAULT_CENTER = {
  lat: 43.3623,
  lon: -8.4115,
};

const BUILDING_PALETTE = [0x96a5b8, 0x7f93a9, 0x9aa2ad, 0xb1b7c1, 0x7e8ca1];

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
    timelineStatusEl.textContent = 'Terreno y edificios en carga';
  }

  if (timelineLabelEl) {
    timelineLabelEl.textContent = 'Arrastra para orbitar';
  }

  if (timelineCountEl) {
    timelineCountEl.textContent = 'Zoom con rueda';
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
      detailPanelTitleEl.textContent = 'Escena base';
    }
    detailPanelBodyEl.innerHTML = '<p class="detail-panel__empty-state">Terreno texturado, edificios con LOD sencillo y cámara orbitable. Usa el ratón para explorar la escena.</p>';
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
    sunLight.position.x = 170 + Math.sin(pulse * 0.8) * 10;
    sunLight.position.z = 120 + Math.cos(pulse * 0.6) * 10;
    renderer.render(scene, camera);
  }

  function cleanup() {
    if (animationFrameId !== null) {
      window.cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
    if (resizeObserver) {
      resizeObserver.disconnect();
    }
    window.removeEventListener('resize', resize);
  }

  window.addEventListener('beforeunload', cleanup, { once: true });

  if (statusEl) {
    statusEl.textContent = 'Escena 3D lista · terreno texturado, edificios LOD y cámara orbitable';
  }

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