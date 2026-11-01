import * as T from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { plates, color, type Plate } from "./ScenePlate";
export function plateRenderer(renderer: T.WebGLRenderer) {
  const scene = new T.Scene(),
    group = new T.Group(),
    camera = new T.PerspectiveCamera(32, 1, 0.1, 90);
  scene.add(group);
  const veil = new T.Mesh(
    new T.PlaneGeometry(100, 100),
    new T.MeshBasicMaterial({
      color: 0x061511,
      transparent: true,
      opacity: 0.82,
      depthWrite: false,
    }),
  );
  veil.position.z = -3;
  veil.renderOrder = -10;
  scene.add(veil);
  const sphere = new T.IcosahedronGeometry(0.09, 1),
    layer = new T.TorusGeometry(0.4, 0.018, 6, 64),
    lockBody = new T.BoxGeometry(0.15, 0.13, 0.07),
    shackle = new T.TorusGeometry(0.052, 0.014, 5, 14, Math.PI),
    lock = mergeGeometries([lockBody, shackle.translate(0, 0.055, 0)]),
    bar = new T.BoxGeometry(0.18, 0.035, 0.04);
  const material = new T.MeshBasicMaterial(),
    lineMaterial = new T.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.87,
    });
  const dummy = new T.Object3D();
  let current: Plate | undefined;

  function clear() {
    for (const obj of [...group.children]) {
      group.remove(obj);
      if (obj instanceof T.Sprite) {
        obj.material.map?.dispose();
        obj.material.dispose();
      }
      if (obj instanceof T.Points) obj.geometry.dispose();
      if (obj instanceof T.InstancedMesh) obj.dispose();
      else if (obj instanceof T.LineSegments) obj.geometry.dispose();
    }
  }
  const glowMaterial = new T.ShaderMaterial({
    vertexColors: true,
    transparent: true,
    depthWrite: false,
    blending: T.AdditiveBlending,
    uniforms: { density: { value: 1 } },
    vertexShader: `varying vec3 tint;uniform float density;void main(){tint=color;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_PointSize=34.*density;}`,
    fragmentShader: `varying vec3 tint;void main(){float d=length(gl_PointCoord-.5)*2.;gl_FragColor=vec4(tint,exp(-5.*d*d)*.5);}`,
  });
  function build(model: Plate) {
    clear();
    current = model;
    for (const [shape, geometry] of [
      ["layer", layer],
      ["lock", lock],
      ["reject", bar],
      ["node", sphere],
    ] as const) {
      const marks = model.marks.filter((m) => (m.shape || "node") === shape);
      if (!marks.length) continue;
      const mesh = new T.InstancedMesh(geometry, material, marks.length);
      marks.forEach((m, i) => {
        dummy.position.set(m.x, m.y, m.z);
        dummy.rotation.set(
          shape === "layer" ? 1.08 : 0,
          shape === "layer" ? 0.18 : 0,
          shape === "reject" ? -0.65 : 0,
        );
        dummy.scale.x = 1 / Math.max(1, Math.min(2.8, innerWidth / 500));
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
        mesh.setColorAt(i, new T.Color(color(m.state)));
      });
      group.add(mesh);
    }
    const bright = model.marks.filter((m) => !m.shape && m.state !== "other");
    const halos = new T.BufferGeometry();
    halos.setAttribute(
      "position",
      new T.Float32BufferAttribute(
        bright.flatMap((m) => [m.x, m.y, m.z]),
        3,
      ),
    );
    halos.setAttribute(
      "color",
      new T.Float32BufferAttribute(
        bright.flatMap((m) => new T.Color(color(m.state)).toArray()),
        3,
      ),
    );
    group.add(new T.Points(halos, glowMaterial));
    for (const mark of model.marks.filter((m) => m.annotate)) {
      const canvas = document.createElement("canvas"),
        ctx = canvas.getContext("2d");
      if (!ctx) continue;
      const label = mark.label.slice(0, 50);
      ctx.font = "500 28px system-ui";
      canvas.width = Math.ceil(ctx.measureText(label).width) + 12;
      canvas.height = 46;
      ctx.font = "500 28px system-ui";
      ctx.fillStyle = "#f6f7f5";
      ctx.fillText(label, 6, 32);
      const texture = new T.CanvasTexture(canvas);
      texture.colorSpace = T.SRGBColorSpace;
      const sprite = new T.Sprite(
        new T.SpriteMaterial({ map: texture, depthTest: false }),
      );
      sprite.center.set(0.5, 0);
      sprite.position.set(mark.x, mark.y + 0.13, mark.z);
      sprite.userData.width = (canvas.width / canvas.height) * 0.37;
      sprite.scale.set(sprite.userData.width, 0.37, 1);
      group.add(sprite);
    }
    const points = model.links.flatMap(([a, b]) =>
      [model.marks[a], model.marks[b]].flatMap((m) => [m.x, m.y, m.z]),
    );
    const g = new T.BufferGeometry();
    g.setAttribute("position", new T.Float32BufferAttribute(points, 3));
    g.setAttribute(
      "color",
      new T.Float32BufferAttribute(
        model.links.flatMap(([a, b]) =>
          [a, b].flatMap((i) =>
            new T.Color(
              model.marks[i].state === "open" ? "#edb47c" : "#86a49b",
            ).toArray(),
          ),
        ),
        3,
      ),
    );
    group.add(new T.LineSegments(g, lineMaterial));
  }
  return {
    draw(host: HTMLElement, time: number, wipe: number) {
      const el = Array.from(document.querySelectorAll<HTMLElement>(".plate-window")).find(candidate =>
          !candidate.closest(".continuation-form") && candidate.getClientRects().length > 0
        ),
        model = el && plates.get(el),
        r = el?.getBoundingClientRect();
      host.classList.toggle("wiping", wipe > 0);
      if (!r || !model || r.bottom <= 0 || r.top >= innerHeight) return;
      const parent = el?.closest<HTMLElement>(".card");
      if (parent) {
        const bounds = parent.getBoundingClientRect();
        const x = r.left - bounds.left,
          y = r.top - bounds.top;
        const hole = `polygon(evenodd,0 0,100% 0,100% 100%,0 100%,0 0,${x}px ${y}px,${x}px ${y + r.height}px,${x + r.width}px ${y + r.height}px,${x + r.width}px ${y}px,${x}px ${y}px)`;
        if (parent.style.getPropertyValue("--graph-hole") !== hole)
          parent.style.setProperty("--graph-hole", hole);
      }
      if (model !== current) build(model);
      renderer.setViewport(r.left, innerHeight - r.bottom, r.width, r.height);
      renderer.setScissor(r.left, innerHeight - r.bottom, r.width, r.height);
      renderer.setScissorTest(true);
      camera.aspect = r.width / r.height;
      camera.position.z = Math.max(6.2, 17 / camera.aspect);
      camera.updateProjectionMatrix();
      group.scale.x = Math.max(1, Math.min(2.8, camera.aspect / 2.9));
      for (const obj of group.children)
        if (obj instanceof T.Sprite)
          obj.scale.x = obj.userData.width / group.scale.x;
      glowMaterial.uniforms.density.value = renderer.getPixelRatio();
      group.rotation.y = 0.12 * Math.sin(time * 0.22);
      group.rotation.x = 0.08 * Math.cos(time * 0.18);
      renderer.autoClear = false;
      renderer.clearDepth();
      renderer.render(scene, camera);
      renderer.autoClear = true;
      renderer.setScissorTest(false);
      renderer.setViewport(0, 0, innerWidth, innerHeight);
    },
    dispose() {
      clear();
      veil.geometry.dispose();
      veil.material.dispose();
      glowMaterial.dispose();
      [
        sphere,
        layer,
        lockBody,
        shackle,
        lock,
        bar,
        material,
        lineMaterial,
      ].forEach((r) => r.dispose());
    },
  };
}
