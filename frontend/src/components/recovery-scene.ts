import { REWIND_DURATION, REWIND_REVEAL, rewindMotion } from "./rewind-motion";
import { angleDelta } from "./motion-math";
import { rewindVortex } from "./rewind-vortex";
import { panelFrames } from "./panel-frames";
import { recoveryWorld } from "./recovery-world";
import * as T from "three";
import { GPUComputationRenderer } from "three/examples/jsm/misc/GPUComputationRenderer.js";

import { plateRenderer } from "./plate-renderer";
const ribbon = `
vec3 ribbon(float a,float b) {
 float r=1.35+.46*cos(3.*a+b*.32);
 return vec3(r*cos(2.*a), r*sin(2.*a)*.78, .7*sin(3.*a+b*.32)) + .10*vec3(cos(b),sin(b),cos(b+a));
}`;
export function mountStudio(
  host: HTMLElement,
  cinematic: boolean,
  ready: () => void,
  intro: {
    active: boolean;
    progress: number;
    rewinding: boolean;
    rewindElapsed: number;
    reveal: () => void;
  },
) {
  const renderer = new T.WebGLRenderer({
    alpha: true,
    antialias: false,
    stencil: false,
    powerPreference: "high-performance",
  });
  const size = cinematic ? 224 : 144;
  const gpu = new GPUComputationRenderer(size, size, renderer);
  const initial = gpu.createTexture(),
    velocity = gpu.createTexture();
  const data = initial.image.data as Float32Array;
  const coords = new Float32Array(size * size * 2);
  for (let i = 0; i < size * size; i++) {
    const a = (((i % size) + 0.5) / size) * 2 * Math.PI,
      b = ((Math.floor(i / size) + 0.5) / size) * 2 * Math.PI,
      r = 1.35 + 0.46 * Math.cos(3 * a + b * 0.32);
    data.set(
      [
        r * Math.cos(2 * a) + 0.1 * Math.cos(b),
        r * Math.sin(2 * a) * 0.78 + 0.1 * Math.sin(b),
        0.7 * Math.sin(3 * a + b * 0.32) + 0.1 * Math.cos(b + a),
        1,
      ],
      i * 4,
    );
    coords.set(
      [((i % size) + 0.5) / size, (Math.floor(i / size) + 0.5) / size],
      i * 2,
    );
  }
  const vel = gpu.addVariable(
    "velocity",
    `uniform vec2 pointer; uniform float impulse, clock, dt;
  void main(){vec2 uv=gl_FragCoord.xy/resolution.xy;vec3 p=texture2D(positionMap,uv).xyz;
  vec2 d=p.xy-pointer; float k=exp(-3.*dot(d,d))*impulse;
  vec3 curl=vec3(cos(p.y+clock)-sin(p.z),cos(p.z)-sin(p.x+clock),cos(p.x+clock)-sin(p.y+clock));
  gl_FragColor=vec4(texture2D(velocity,uv).xyz*exp(-3.*dt)+dt*(curl*.075+vec3(-d.y,d.x,0.)*k*18.),1.);}`,
    velocity,
  );
  const pos = gpu.addVariable(
    "positionMap",
    ribbon +
      `uniform float clock,dt;void main(){vec2 uv=gl_FragCoord.xy/resolution.xy;
  vec3 p=texture2D(positionMap,uv).xyz;float seed=fract(sin(dot(uv,vec2(73.4,219.6)))*43758.5);
  float a=uv.x*6.28318+clock*.09;
  vec3 home=ribbon(a+seed*.014,uv.y*6.28318);
  if(uv.y>.88){float spread=pow(seed,2.)*1.8;home+=spread*vec3(sin(seed*320.),cos(uv.x*76.+seed),sin(uv.y*171.));}
  gl_FragColor=vec4(mix(p,home,1.-exp(-2.*dt))+texture2D(velocity,uv).xyz*dt,1.);}`,
    initial,
  );
  for (const v of [vel, pos]) {
    gpu.setVariableDependencies(v, [vel, pos]);
    Object.assign(v.material.uniforms, {
      clock: { value: 0 },
      dt: { value: 0.016 },
    });
  }
  const pointer = new T.Vector2(12, 12);
  const ray = new T.Raycaster(),
    ndc = new T.Vector2(),
    hit = new T.Vector3(),
    surface = new T.Plane(new T.Vector3(0, 0, 1), 0);
  Object.assign(vel.material.uniforms, {
    pointer: { value: pointer },
    impulse: { value: 0 },
  });
  if (gpu.init()) {
    gpu.dispose();
    renderer.dispose();
    throw Error("GPU simulation unavailable");
  }
  const scene = new T.Scene(),
    camera = new T.PerspectiveCamera(38, 1, 0.1, 40);
  const geo = new T.BufferGeometry();
  geo.setAttribute(
    "position",
    new T.BufferAttribute(new Float32Array(size * size * 3), 3),
  );
  geo.setAttribute("lookup", new T.BufferAttribute(coords, 2));
  const material = new T.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: T.AdditiveBlending,
    uniforms: { field: { value: initial }, ratio: { value: 1 } },
    vertexShader: `attribute vec2 lookup;uniform sampler2D field;uniform float ratio;varying float light,blur;
    void main(){vec3 p=texture2D(field,lookup).xyz;vec4 mv=modelViewMatrix*vec4(p,1.);gl_Position=projectionMatrix*mv;
    light=.24+.76*pow(abs(sin(lookup.y*28.+p.x)),6.);blur=smoothstep(.4,2.,abs(p.z-.35));gl_PointSize=ratio*(1.25+blur*2.)*5./-mv.z;}`,
    fragmentShader: `varying float light,blur;void main(){float d=length(gl_PointCoord-.5)*2.;float f=exp(-3.*d*d);gl_FragColor=vec4(mix(vec3(.025,.32,.23),vec3(.82,1.,.62),light*light),f*light*(.48-.22*blur));}`,
  });
  const field = new T.Points(geo, material);
  field.frustumCulled = false;
  scene.add(field);
  const world = recoveryWorld(scene);
  const vortex = rewindVortex(scene);
  const responsivePointer = new T.Vector2();
  const target = new T.WebGLRenderTarget(1, 1);
  const post = new T.Scene(),
    ortho = new T.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const composite = new T.ShaderMaterial({
    uniforms: {
      tex: { value: target.texture },
      px: { value: new T.Vector2() },
      time: { value: 0 },
      wipe: { value: 0 },
      eclipse: { value: 0 },
    },
    vertexShader:
      "varying vec2 v;void main(){v=uv;gl_Position=vec4(position.xy,0.,1.);}",
    fragmentShader: `varying vec2 v;uniform sampler2D tex;uniform vec2 px;uniform float time,wipe,eclipse;
    void main(){vec2 e=v-.5;vec2 shift=e*dot(e,e)*.002;vec3 c=texture2D(tex,v).rgb;c.r=texture2D(tex,v+shift).r;
    for(int i=0;i<8;i++){float a=float(i)*.7854;vec3 halo=texture2D(tex,v+vec2(cos(a),sin(a))*px*4.).rgb;c+=max(halo-.25,0.)*.095;}
    float grain=fract(sin(dot(gl_FragCoord.xy+fract(time),vec2(12.9898,78.233)))*43758.5);
    vec3 base=mix(vec3(.012,.035,.032),vec3(.052,.14,.116),1.-smoothstep(.0,.75,length(e)));
    float veil=wipe>0.?1.-smoothstep(.0,.25,abs(v.x+v.y*.12-wipe*1.65+.25)):0.;
    float mist=exp(-9.*abs(v.y-.76+.24*v.x+.035*sin(v.x*9.+time*.13)))*smoothstep(.15,.8,v.x);
    base+=vec3(.012,.045,.030)*mist;
    float progress=wipe*1.9-.45;
    float distanceToFront=abs(v.x+.11*v.y+.014*sin(v.y*13.+time)-progress);
    float coverage=wipe>0.?1.-smoothstep(.04,.12+sin(wipe*3.14159)*.23,distanceToFront):1.;
    vec3 result=(base+c)*(1.-.48*dot(e,e))+grain*.012+veil*.10;
    float eclipseMask=1.-smoothstep(.05,.85,length(vec2(e.x*.75,e.y)));
    result*=1.-eclipse*(.7+.28*eclipseMask);
    gl_FragColor=vec4(result*coverage,coverage);}`,
  });
  const plane = new T.PlaneGeometry(2, 2);
  post.add(new T.Mesh(plane, composite));
  const plate = plateRenderer(renderer);
  const frames = panelFrames(renderer);
  host.appendChild(renderer.domElement);
  let ratio = Math.min(devicePixelRatio, cinematic ? 1.5 : 1),
    raf = 0,
    last = 0,
    t = 0,
    slow = 0,
    wipe = 0,
    scroll = 0,
    impulse = 0;
  const samples: number[] = [];
  let measureAt = 0;
  const resize = () => {
    renderer.setPixelRatio(ratio);
    renderer.setSize(innerWidth, innerHeight);
    const simulationRatio = Math.min(ratio, 1.15);
    target.setSize(innerWidth * simulationRatio, innerHeight * simulationRatio);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    material.uniforms.ratio.value = simulationRatio;
    composite.uniforms.px.value.set(1 / target.width, 1 / target.height);
  };
  const move = (e: PointerEvent) => {
    ndc.set(
      (e.clientX / innerWidth) * 2 - 1,
      1 - (e.clientY / innerHeight) * 2,
    );
    ray.setFromCamera(ndc, camera);
    if (ray.ray.intersectPlane(surface, hit)) {
      field.worldToLocal(hit);
      pointer.set(hit.x, hit.y);
    }
    impulse = Math.min(
      2,
      impulse + Math.hypot(e.movementX, e.movementY) * 0.05,
    );
  };
  const leave = () => { ndc.set(0, 0); pointer.set(12, 12); impulse = 0; };
  const out = (event: PointerEvent) => { if (!event.relatedTarget) leave(); };
  const routeAngles: Record<string, number> = {
    overview: 0,
    incidents: 0.8,
    incident: 1.1,
    projects: 1.6,
    continuity: 2.4,
    demo: 3.2,
    evidence: 3.8,
    settings: 4.3,
  };
  const angle = () => routeAngles[location.hash.slice(1).split("/")[0]] || 0;
  let yaw = angle(),
    destinationYaw = yaw;
  const route = () => {
    destinationYaw = angle();
    wipe = 0.001;
  };
  const previousCamera = new T.Vector3();
  const previousCameraRotation = new T.Quaternion();
  const previousField = new T.Vector3();
  const previousFieldRotation = new T.Quaternion();
  const previousFieldScale = new T.Vector3();
  camera.position.z = intro.active ? 6.3 : 5.2;
  const frame = (now: number) => {
    previousCamera.copy(camera.position);
    previousCameraRotation.copy(camera.quaternion);
    previousField.copy(field.position);
    previousFieldRotation.copy(field.quaternion);
    previousFieldScale.copy(field.scale);
    const elapsed = last ? (now - last) / 1000 : 0.016,
      dt = Math.min(elapsed, 0.05);
    last = now;
    t += dt;
    if (elapsed < 1) samples.push(elapsed);
    if (samples.length >= 90) {
      const total = samples.reduce((a, b) => a + b, 0);
      host.dataset.frameStats = JSON.stringify({
        fps: Math.round(samples.length / total),
        p95ms: Math.round(
          samples.sort((a, b) => a - b)[Math.floor(samples.length * 0.95)] *
            1000,
        ),
        dpr: ratio,
        particles: Math.min(geo.drawRange.count, size * size),
        sample: ++measureAt,
      });
      slow = total / samples.length > 0.0195 ? slow + 1 : 0;
      samples.length = 0;
    }

    if (slow >= 2 && ratio > 0.65) {
      ratio = Math.max(0.65, ratio * 0.8);
      if (ratio < 1) geo.setDrawRange(0, Math.floor(size * size * 0.75));
      resize();
      slow = 0;
    }
    scroll += (window.scrollY / innerHeight - scroll) * (1 - Math.exp(-5 * dt));
    impulse *= Math.exp(-4 * dt);
    for (const v of [vel, pos]) {
      v.material.uniforms.clock.value = t;
      v.material.uniforms.dt.value = dt;
    }
    vel.material.uniforms.impulse.value = impulse;
    gpu.compute();
    material.uniforms.field.value = gpu.getCurrentRenderTarget(pos).texture;
    const login = document.body.classList.contains("studio-login");
    field.position.set(
      (login ? -0.21 : 0.31) * camera.aspect * 4,
      login ? 0.76 : 1.02,
      0,
    );
    yaw += angleDelta(yaw, destinationYaw) * (1 - Math.exp(-5 * dt));
    field.rotation.set(
      -0.28 + 0.07 * Math.sin(t * 0.14),
      t * 0.09 + scroll * 0.14 + yaw,
      -0.48,
    );
    field.scale.setScalar(login ? 0.78 : 0.74);
    camera.position.z =
      5.2 - 0.18 * Math.tanh(scroll) - 0.18 * Math.sin(wipe * Math.PI);
    camera.position.x = 0.025 * Math.tanh(pointer.x);
    camera.position.y = 0.022 * Math.tanh(pointer.y);
    responsivePointer.lerp(ndc, 1 - Math.exp(-dt * 3.4));
    const opening = intro.active ? intro.progress : null;
    world.update(
      t,
      dt,
      location.hash.slice(1).split("/")[0],
      opening,
      camera.aspect,
      scroll,
      responsivePointer.x,
      responsivePointer.y,
      login,
    );
    if (opening !== null) {
      const phase = opening * 4;
      camera.position.set(
        0.2 * Math.sin(phase * 1.4) + responsivePointer.x * 0.15,
        0.12 * Math.sin(phase * 1.2) + responsivePointer.y * 0.1,
        6.3 - 0.6 * Math.sin(phase * Math.PI),
      );
      camera.lookAt(0, 0, -0.3);
      field.position.set(camera.aspect * 0.52, 0.2, -1.15);
      field.rotation.set(-0.28, phase * 0.48, -0.48);
      field.scale.setScalar(0.76);
    } else {
      camera.rotation.set(0, 0, 0);
      camera.position.x += ndc.x * 0.12;
      camera.position.y += ndc.y * 0.09;
    }
    let rewindStrength = 0;
    if (intro.rewinding) {
      const before = intro.rewindElapsed;
      intro.rewindElapsed += dt;
      const progress = Math.min(1, intro.rewindElapsed / REWIND_DURATION);
      const motion = rewindMotion(progress);
      rewindStrength = motion.strength;
      world.rewind(motion.turn, motion.bank);
      field.rotation.z -= motion.turn;
      composite.uniforms.eclipse.value = motion.shadow;
      host.dataset.rewinding = progress < REWIND_REVEAL ? "depart" : "arrive";
      if (before < REWIND_DURATION * REWIND_REVEAL && motion.reveal) intro.reveal();
      camera.position.x *= 1 - rewindStrength;
      camera.position.y *= 1 - rewindStrength;
      camera.position.z = T.MathUtils.lerp(
        camera.position.z,
        3.8,
        rewindStrength,
      );
      camera.rotation.z += Math.sin(progress * Math.PI) * 0.16;
      vortex.update(progress, rewindStrength, ratio);
      if (progress === 1) {
        intro.rewinding = false;
        delete host.dataset.rewinding;
        vortex.update(0, 0, ratio);
        world.rewind(0, 0);
        composite.uniforms.eclipse.value = 0;
      }
    } else {
      vortex.update(0, 0, ratio);
      world.rewind(0, 0);
      composite.uniforms.eclipse.value = 0;
    }
    const settle = 1 - Math.exp(-7.5 * dt);
    camera.position.lerpVectors(previousCamera, camera.position, settle);
    camera.quaternion.copy(previousCameraRotation.slerp(camera.quaternion, settle));
    field.position.lerpVectors(previousField, field.position, settle);
    field.quaternion.copy(previousFieldRotation.slerp(field.quaternion, settle));
    field.scale.lerpVectors(previousFieldScale, field.scale, settle);
    renderer.setRenderTarget(target);
    renderer.render(scene, camera);
    renderer.setRenderTarget(null);
    composite.uniforms.time.value = t;
    composite.uniforms.wipe.value = wipe;
    renderer.render(post, ortho);
    if (opening === null && !intro.rewinding) {
      frames.draw(t, ndc);
      plate.draw(host, t, wipe);
    }
    if (wipe) {
      wipe += dt / 0.8;
      if (wipe >= 1) wipe = 0;
    }
    if (!host.dataset.ready) {
      host.dataset.ready = "true";
      ready();
    }
    raf = requestAnimationFrame(frame);
  };
  const visibility = () => {
    cancelAnimationFrame(raf);
    last = 0;
    if (!document.hidden && !renderer.getContext().isContextLost()) raf = requestAnimationFrame(frame);
  };
  const contextLost = (event: Event) => {
    event.preventDefault();
    cancelAnimationFrame(raf);
    renderer.domElement.style.opacity = "0";
    delete host.dataset.ready;
    document.documentElement.dataset.motion = "off";
  };
  const contextRestored = () => window.dispatchEvent(new Event("ctrlz-quality"));
  renderer.domElement.addEventListener("webglcontextlost", contextLost);
  renderer.domElement.addEventListener("webglcontextrestored", contextRestored);
  resize();
  visibility();
  addEventListener("resize", resize);
  addEventListener("pointermove", move);
  addEventListener("pointerout", out);
  addEventListener("blur", leave);
  addEventListener("hashchange", route);
  document.addEventListener("visibilitychange", visibility);
  return () => {
    cancelAnimationFrame(raf);
    removeEventListener("resize", resize);
    removeEventListener("pointermove", move);
    removeEventListener("pointerout", out);
    removeEventListener("blur", leave);
    removeEventListener("hashchange", route);
    document.removeEventListener("visibilitychange", visibility);
    renderer.domElement.removeEventListener("webglcontextlost", contextLost);
    renderer.domElement.removeEventListener("webglcontextrestored", contextRestored);
    frames.dispose();
    vortex.dispose();
    delete host.dataset.rewinding;
    world.dispose();
    plate.dispose();
    host.classList.remove("plate-active");
    host.style.removeProperty("clip-path");
    gpu.dispose();
    geo.dispose();
    material.dispose();
    plane.dispose();
    composite.dispose();
    target.dispose();
    renderer.dispose();
    renderer.domElement.remove();
    host.classList.remove("wiping");
    delete host.dataset.frameStats;
    delete host.dataset.ready;
  };
}
