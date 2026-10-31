import * as T from "three";

const modes: Record<string, number> = {
  overview: 0,
  projects: 1,
  incidents: 2,
  incident: 2,
  continuity: 3,
  demo: 4,
  evidence: 5,
  settings: 6,
};

const shortArc = (angle: number) =>
  Math.atan2(Math.sin(angle), Math.cos(angle));

function introPose(index: number, stage: number) {
  const a = (index / 96) * Math.PI * 2;
  if (stage === 1) {
    const row = index % 12,
      layer = Math.floor(index / 12);
    return [
      (row - 5.5) * 0.23 + (layer === 4 ? 0.6 : 0),
      (layer - 3.5) * 0.27,
      (row - 5.5) * 0.055,
      0.15 + layer * 0.065,
      0.3,
      Math.PI / 2,
    ];
  }
  if (stage === 2) {
    const side = index % 2,
      slot = index >> 1,
      row = Math.floor(slot / 8),
      col = slot % 8;
    return [
      (side ? 1 : -1) * (0.4 + col * 0.18),
      (row - 2.5) * 0.29 + (side ? 0.16 : -0.16),
      0.16 * Math.sin(col * 0.32),
      0.3,
      side ? 0.35 : -0.35,
      side ? 0.15 : -0.15,
    ];
  }
  if (stage === 3) {
    const arc = 0.47 + (index / 96) * (Math.PI * 2 - 1.02);
    return [
      Math.cos(arc) * 1.63,
      Math.sin(arc) * 1.63,
      0.18 * Math.sin(2 * arc),
      0.43,
      0.38 * Math.sin(a * 2),
      arc - Math.PI / 2,
    ];
  }
  return [
    Math.cos(a) * 1.6,
    Math.sin(a) * 1.6,
    0.25 * Math.sin(3 * a),
    0.43,
    0.38 * Math.sin(a * 2),
    a - Math.PI / 2,
  ];
}

export function recoveryWorld(scene: T.Scene) {
  const world = new T.Group();
  scene.add(world);
  const metal = new T.ShaderMaterial({
    uniforms: { time: { value: 0 } },
    vertexShader: `varying vec3 n,v;varying float stripe;
    void main(){mat4 model=modelMatrix*instanceMatrix;vec3 p=(model*vec4(position,1.)).xyz;
      n=normalize(mat3(model)*normal);v=normalize(cameraPosition-p);stripe=position.y;
      gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}`,
    fragmentShader: `varying vec3 n,v;varying float stripe;uniform float time;
    void main(){vec3 r=reflect(-normalize(v),normalize(n));
      float key=exp(-9.*abs(r.y-.48+.33*r.x));
      float rim=pow(1.-abs(dot(normalize(n),normalize(v))),3.);
      float rail=exp(-23.*abs(r.x+.25*sin(time*.22)));
      vec3 alloy=mix(vec3(.017,.075,.052),vec3(.12,.37,.235),.5+.5*r.y);
      vec3 c=alloy+vec3(.69,.89,.62)*key+vec3(.18,.44,.29)*rim+vec3(.64,.82,.69)*rail;
      gl_FragColor=vec4(c*(.96+.04*cos(stripe*160.)),1.);}`,
  });
  const blade = new T.Shape();
  blade.moveTo(-0.06, -0.53);
  blade.quadraticCurveTo(0.21, -0.13, 0.15, 0.48);
  blade.lineTo(0.05, 0.55);
  blade.quadraticCurveTo(0.1, 0.05, -0.12, -0.38);
  blade.closePath();
  const geometry = new T.ExtrudeGeometry(blade, {
    depth: 0.065,
    bevelEnabled: true,
    bevelSegments: 2,
    bevelSize: 0.018,
    bevelThickness: 0.018,
    curveSegments: 9,
  });
  const count = 96,
    fins = new T.InstancedMesh(geometry, metal, count),
    dummy = new T.Object3D();
  fins.frustumCulled = false;
  world.add(fins);
  const guideGeometry = new T.BufferGeometry(),
    lines: number[] = [];
  for (let i = -18; i <= 18; i++) {
    lines.push(i, -2.1, -28, i, -2.1, 9, -20, -2.1, i, 20, -2.1, i);
  }
  guideGeometry.setAttribute(
    "position",
    new T.Float32BufferAttribute(lines, 3),
  );
  const guideMaterial = new T.LineBasicMaterial({
    color: 0x78ab90,
    transparent: true,
    opacity: 0.12,
    depthWrite: false,
  });
  const floor = new T.LineSegments(guideGeometry, guideMaterial);
  scene.add(floor);
  const stars = new Float32Array(2400 * 3);
  for (let i = 0; i < stars.length; i += 3) {
    stars[i] = (Math.random() - 0.5) * 30;
    stars[i + 1] = (Math.random() - 0.5) * 15;
    stars[i + 2] = 7 - Math.random() * 31;
  }
  const dustGeometry = new T.BufferGeometry();
  dustGeometry.setAttribute("position", new T.BufferAttribute(stars, 3));
  const dustMaterial = new T.PointsMaterial({
    size: 0.017,
    color: 0xc5f2a5,
    transparent: true,
    opacity: 0.58,
    depthWrite: false,
  });
  const dust = new T.Points(dustGeometry, dustMaterial);
  scene.add(dust);
  const positions = new Float32Array(count * 3),
    rotations = new Float32Array(count * 3);
  const worldTarget = new T.Vector3();
  const targetRotation = new T.Euler();
  const targetQuaternion = new T.Quaternion();
  let first = true;
  return {
    update(
      t: number,
      dt: number,
      route: string,
      opening: number | null,
      aspect: number,
      scroll: number,
      mx: number,
      my: number,
      login: boolean,
    ) {
      const mode = login ? 0 : (modes[route] ?? 0),
        mix = first ? 1 : 1 - Math.exp(-4.5 * dt);
      metal.uniforms.time.value = t;
      const spin = t * 0.13;
      for (let i = 0; i < count; i++) {
        const u = i / count,
          a = u * Math.PI * 2,
          k = i * 3,
          theta = a + spin;
        let x = Math.cos(theta) * 1.6,
          y = Math.sin(theta) * 1.6,
          z = 0.25 * Math.sin(3 * a + t * 0.35),
          rz = theta - Math.PI / 2,
          ry = 0.38 * Math.sin(a * 2 + t * 0.25),
          rx = 0.43;
        if (mode === 1 || mode === 5) {
          const row = i % 12,
            col = Math.floor(i / 12);
          x = (row - 5.5) * 0.28;
          y = (col - 3.5) * 0.25;
          z = 0.55 * Math.sin(row * 0.46 + col * 0.28 + spin);
          rz = mode === 5 ? Math.PI / 2 : 0.25;
          ry = spin + 0.25 * row;
          rx = 0.25 * col;
        } else if (mode === 2 || mode === 4) {
          const h = (i >> 1) / 47,
            twist =
              h * Math.PI * (mode === 4 ? 4 : 2.8) + (i % 2) * Math.PI + spin;
          x = Math.cos(twist) * 0.94;
          y = (h - 0.5) * 3.9;
          z = Math.sin(twist) * 0.94;
          rz = twist * 0.15;
          ry = twist;
          rx = 1.1;
        } else if (mode === 3 || mode === 6) {
          const layer = i % 4,
            theta = ((i >> 2) / 24) * Math.PI * 2 + spin + layer * 0.14;
          x = Math.cos(theta) * (1.18 + layer * 0.1);
          y = Math.sin(theta) * (1.18 + layer * 0.1);
          z = (layer - 1.5) * 0.39;
          rz = theta;
          ry = 0.42 + layer * 0.15;
          rx = mode === 6 ? 0.78 : 0.18;
        }
        if (opening !== null) {
          const phase = opening * 4,
            from = Math.min(3, Math.floor(phase)),
            fraction = phase - from;
          const blend = T.MathUtils.smoothstep(fraction, 0.18, 0.82),
            start = introPose(i, from),
            end = introPose(i, from + 1);
          for (let axis = 0; axis < 3; axis++) {
            positions[k + axis] = T.MathUtils.lerp(
              start[axis],
              end[axis],
              blend,
            );
            rotations[k + axis] =
              start[axis + 3] +
              shortArc(end[axis + 3] - start[axis + 3]) * blend;
          }
        } else {
          positions[k] += (x - positions[k]) * mix;
          positions[k + 1] += (y - positions[k + 1]) * mix;
          positions[k + 2] += (z - positions[k + 2]) * mix;
          rotations[k] += shortArc(rx - rotations[k]) * mix;
          rotations[k + 1] += shortArc(ry - rotations[k + 1]) * mix;
          rotations[k + 2] += shortArc(rz - rotations[k + 2]) * mix;
        }
        dummy.position.fromArray(positions, k);
        dummy.rotation.set(rotations[k], rotations[k + 1], rotations[k + 2]);
        dummy.updateMatrix();
        fins.setMatrixAt(i, dummy.matrix);
      }
      first = false;
      fins.instanceMatrix.needsUpdate = true;
      const intro = opening !== null;
      world.position.lerp(worldTarget.set(
        intro ? aspect * 0.49 : login ? -aspect * 0.95 : aspect * 0.98,
        intro ? 0.12 : login ? 0.62 : 0.18 + 0.38 * Math.sin(scroll * 0.85),
        intro ? 0 : -0.55,
      ), mix);
      targetRotation.set(
        0.25 + my * 0.11 + 0.12 * Math.sin(scroll * 0.8),
        -0.34 + mx * 0.16 + scroll * 0.26 + Math.sin(t * 0.13) * 0.18,
        -0.34 + 0.07 * Math.sin(t * 0.17),
      );
      if (opening !== null)
        targetRotation.set(
          0.25 + my * 0.13,
          -0.34 + opening * 0.6 + mx * 0.19,
          -0.34 + mx * 0.025,
        );
      world.quaternion.slerp(targetQuaternion.setFromEuler(targetRotation), mix);
      world.scale.setScalar(T.MathUtils.lerp(world.scale.x, intro ? 1 : login ? 0.82 : 1.02, mix));
      floor.position.z = (scroll * 0.65 + t * 0.09) % 1;
      dust.rotation.y = t * 0.014;
      dust.position.y = 0.08 * Math.sin(t * 0.19);
    },
    dispose() {
      scene.remove(world, floor, dust);
      fins.dispose();
      [
        geometry,
        metal,
        guideGeometry,
        guideMaterial,
        dustGeometry,
        dustMaterial,
      ].forEach((v) => v.dispose());
    },
  };
}
