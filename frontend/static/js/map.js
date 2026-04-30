function initMap() {
  const mapEl = document.getElementById('map');
  if (!mapEl) return;

  const centerLatLng = [40.4168, -3.7038];
  const map = L.map('map', { zoomControl: true }).setView(centerLatLng, 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  // Three.js renderer overlay
  const size = map.getSize();
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setSize(size.x, size.y);
  renderer.domElement.style.position = 'absolute';
  renderer.domElement.style.top = '0';
  renderer.domElement.style.left = '0';
  renderer.domElement.style.pointerEvents = 'none';
  mapEl.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-size.x / 2, size.x / 2, size.y / 2, -size.y / 2, -1000, 1000);
  camera.position.z = 100;

  const light = new THREE.DirectionalLight(0xffffff, 0.8);
  light.position.set(0, 0, 1).normalize();
  scene.add(light);

  // demo object: a cube positioned at a geographic coordinate
  const geometry = new THREE.BoxGeometry(30, 30, 30);
  const material = new THREE.MeshNormalMaterial();
  const cube = new THREE.Mesh(geometry, material);
  scene.add(cube);

  const targetLatLng = centerLatLng;

  function latLngToScenePosition(latlng) {
    const p = map.latLngToLayerPoint(latlng);
    const w = map.getSize().x;
    const h = map.getSize().y;
    const x = p.x - w / 2;
    const y = h / 2 - p.y;
    return new THREE.Vector3(x, y, 0);
  }

  function updateOverlay() {
    const s = map.getSize();
    renderer.setSize(s.x, s.y);
    camera.left = -s.x / 2;
    camera.right = s.x / 2;
    camera.top = s.y / 2;
    camera.bottom = -s.y / 2;
    camera.updateProjectionMatrix();

    const pos = latLngToScenePosition(targetLatLng);
    cube.position.copy(pos);
  }

  map.on('move zoom resize', function () {
    updateOverlay();
  });

  let last = 0;
  function animate(t) {
    requestAnimationFrame(animate);
    const dt = t - last;
    last = t;
    cube.rotation.x += 0.001 * dt;
    cube.rotation.y += 0.0012 * dt;
    renderer.render(scene, camera);
  }

  updateOverlay();
  requestAnimationFrame(animate);
}

// Expose for HTML onload
if (typeof window !== 'undefined') window.initMap = initMap;
