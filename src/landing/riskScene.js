import * as THREE from "three";

// A spatial explanation, rendered only on changes. No permanent animation loop.
export function mountScene(host) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.domElement.setAttribute("aria-hidden", "true");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
  scene.add(new THREE.HemisphereLight(0xf0efdf, 0x3e4838, 3));
  const light = new THREE.DirectionalLight(0xffffff, 3);
  light.position.set(-4, 8, 5);
  scene.add(light);
  const mat = (color) =>
    new THREE.MeshStandardMaterial({ color, roughness: 0.68, metalness: 0.22 });
  const steel = mat(0x8c9682),
    dark = mat(0x444c3e),
    pale = mat(0xdadac9),
    accent = mat(0xc8a367);
  const add = (parent, geometry, material, x, y, z) => {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    parent.add(mesh);
    return mesh;
  };
  const box = (parent, w, h, d, m, x, y, z) =>
    add(parent, new THREE.BoxGeometry(w, h, d), m, x, y, z);
  const ground = add(
    scene,
    new THREE.PlaneGeometry(13, 7),
    mat(0x30382c),
    0,
    -0.03,
    0,
  );
  ground.rotation.x = -Math.PI / 2;
  const machine = new THREE.Group();
  machine.position.x = 2.6;
  scene.add(machine);
  box(machine, 2.2, 0.22, 1.8, dark, 0, 0.11, 0);
  box(machine, 0.38, 2.7, 0.5, steel, -0.8, 1.55, -0.5);
  box(machine, 0.38, 2.7, 0.5, steel, 0.8, 1.55, -0.5);
  box(machine, 2, 0.45, 0.65, steel, 0, 2.65, -0.5);
  box(machine, 1.5, 0.3, 1.5, steel, 0, 1.1, 0);
  box(machine, 0.65, 0.8, 0.65, dark, 0, 1.95, -0.3);
  for (let i = 0; i < 7; i++) {
    const roller = add(
      machine,
      new THREE.CylinderGeometry(0.09, 0.09, 1.6, 16),
      steel,
      0,
      0.65,
      -0.8 + i * 0.26,
    );
    roller.rotation.z = Math.PI / 2;
  }
  const person = new THREE.Group();
  scene.add(person);
  add(person, new THREE.SphereGeometry(0.18, 24, 16), pale, 0, 1.85, 0);
  add(
    person,
    new THREE.SphereGeometry(0.2, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2),
    accent,
    0,
    1.88,
    0,
  );
  add(person, new THREE.CapsuleGeometry(0.21, 0.35, 6, 16), pale, 0, 1.35, 0);
  for (const side of [-1, 1]) {
    const leg = add(
      person,
      new THREE.CapsuleGeometry(0.075, 0.66, 6, 12),
      dark,
      side * 0.13,
      0.55,
      0,
    );
    leg.rotation.z = side * 0.04;
    const arm = add(
      person,
      new THREE.CapsuleGeometry(0.065, 0.48, 6, 12),
      pale,
      side * 0.29,
      1.25,
      0,
    );
    arm.rotation.z = side * 0.16;
    box(person, 0.2, 0.12, 0.35, dark, side * 0.13, 0.09, 0.06);
  }
  const bounds = [
    new THREE.BoxHelper(person, 0xb7c39f),
    new THREE.BoxHelper(machine, 0xb7c39f),
  ];
  bounds.forEach((bound) => scene.add(bound));
  const ring = add(
    scene,
    new THREE.RingGeometry(1.7, 1.73, 80),
    new THREE.MeshBasicMaterial({ color: 0xb7c39f, side: THREE.DoubleSide }),
    2.6,
    0.015,
    0,
  );
  ring.rotation.x = -Math.PI / 2;
  let current = 0,
    visible = true,
    frame = 0,
    disposed = false;
  function render() {
    frame = 0;
    if (!disposed && visible && !document.hidden)
      renderer.render(scene, camera);
  }
  function requestRender() {
    if (!frame && !disposed) frame = requestAnimationFrame(render);
  }
  function update(p) {
    current = p;
    person.position.x = -3 + p * 4;
    person.rotation.y = -0.2 + p * 0.35;
    camera.position.set(-0.5 + p * 0.65, 4.6 - p * 0.7, 10.8 - p * 0.4);
    camera.lookAt(0.3, 1, 0);
    const color = p < 0.45 ? 0xb7c39f : p < 0.82 ? 0xd8ad62 : 0xdb8066;
    ring.material.color.set(color);
    bounds.forEach((bound) => {
      bound.update();
      bound.material.color.set(color);
      bound.visible = host.classList.contains("vision-on");
    });
    requestRender();
  }
  const visionObserver = new MutationObserver(() => update(current));
  visionObserver.observe(host, {
    attributes: true,
    attributeFilter: ["class"],
  });
  const resize = new ResizeObserver(() => {
    const { width, height } = host.getBoundingClientRect();
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    update(current);
  });
  const visibility = new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    if (visible) requestRender();
  });
  const onVisibility = () => requestRender();
  const onLost = (e) => {
    e.preventDefault();
    host.classList.remove("has-webgl");
  };
  const onRestored = () => {
    host.classList.add("has-webgl");
    requestRender();
  };
  renderer.domElement.addEventListener("webglcontextlost", onLost);
  renderer.domElement.addEventListener("webglcontextrestored", onRestored);
  host.appendChild(renderer.domElement);
  host.classList.add("has-webgl");
  resize.observe(host);
  visibility.observe(host);
  document.addEventListener("visibilitychange", onVisibility);
  update(0);
  return {
    update,
    dispose() {
      disposed = true;
      cancelAnimationFrame(frame);
      resize.disconnect();
      visibility.disconnect();
      visionObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      renderer.domElement.removeEventListener("webglcontextlost", onLost);
      renderer.domElement.removeEventListener(
        "webglcontextrestored",
        onRestored,
      );
      const materials = new Set();
      scene.traverse((obj) => {
        obj.geometry?.dispose();
        if (obj.material) materials.add(obj.material);
      });
      materials.forEach((m) => m.dispose());
      renderer.dispose();
      renderer.domElement.remove();
      host.classList.remove("has-webgl");
    },
  };
}
