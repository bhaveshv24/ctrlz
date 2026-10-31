import * as T from "three";

const surfaces =
  ".main-content :is(.card,.metric,.scenario-card,.command-banner,.demo-workspace,.workspace-tabs,.scene-plate),.login-content";
export function panelFrames(renderer: T.WebGLRenderer) {
  const scene = new T.Scene(),
    camera = new T.OrthographicCamera(0, 1, 1, 0, 0.1, 200);
  camera.position.z = 100;
  const geometry = new T.BoxGeometry(1, 1, 1);
  const material = new T.ShaderMaterial({
    uniforms: { time: { value: 0 }, pointer: { value: new T.Vector2() } },
    vertexShader: `varying vec2 panelUv;varying vec3 face;varying vec2 screen;
    void main(){panelUv=uv;face=normal;vec4 p=instanceMatrix*vec4(position,1.);
      gl_Position=projectionMatrix*modelViewMatrix*p;screen=gl_Position.xy;}`,
    fragmentShader: `varying vec2 panelUv,screen;varying vec3 face;uniform float time;uniform vec2 pointer;
    void main(){vec2 edge=min(panelUv,1.-panelUv)/max(fwidth(panelUv),vec2(.00001));
      float line=1.-smoothstep(.2,1.9,min(edge.x,edge.y));
      float glint=exp(-7.*abs(fract(panelUv.x*.65+panelUv.y*.35-time*.085)-.5));
      float nearby=exp(-2.*length(screen-pointer));
      vec3 steel=mix(vec3(.024,.10,.075),vec3(.53,.82,.60),line*(.22+glint*.72+nearby*.2));
      float alpha=face.z>.5?line*.86:.85;
      gl_FragColor=vec4(steel,alpha);}`,
    transparent: true,
    depthWrite: false,
  });
  const frames = new T.InstancedMesh(geometry, material, 64),
    dummy = new T.Object3D();
  frames.frustumCulled = false;
  scene.add(frames);
  let dirty = true,
    panels: HTMLElement[] = [];
  let measuredAt = -1;
  let rectangles: DOMRect[] = [];
  const observer = new MutationObserver(() => {
    dirty = true;
  });
  observer.observe(document.querySelector(".world-interface")!, {
    childList: true,
    subtree: true,
  });
  return {
    draw(time: number, pointer: T.Vector2) {
      if (dirty) {
        panels = Array.from(document.querySelectorAll<HTMLElement>(surfaces));
        dirty = false;
        measuredAt = -1;
      }
      // DOM reads are batched at 30 Hz instead of forcing layout for every GPU frame.
      if (measuredAt < 0 || time - measuredAt >= 1 / 30) {
        rectangles = panels.map(el => el.getBoundingClientRect());
        measuredAt = time;
      }
      camera.right = innerWidth;
      camera.top = innerHeight;
      camera.updateProjectionMatrix();
      let count = 0;
      for (const r of rectangles) {
        if (!r.width || r.bottom < 0 || r.top > innerHeight || count === 64)
          continue;
        const depth = 5 + Math.min(4, r.height / 100);
        dummy.position.set(
          r.left + r.width / 2,
          innerHeight - r.top - r.height / 2 - depth * 0.5,
          0,
        );
        dummy.scale.set(r.width + 3, r.height + depth, depth);
        dummy.rotation.set(-0.027, 0.008 * pointer.x, 0);
        dummy.updateMatrix();
        frames.setMatrixAt(count++, dummy.matrix);
      }
      frames.count = count;
      frames.instanceMatrix.needsUpdate = true;
      material.uniforms.time.value = time;
      material.uniforms.pointer.value.copy(pointer);
      renderer.autoClear = false;
      renderer.clearDepth();
      renderer.render(scene, camera);
      renderer.autoClear = true;
    },
    dispose() {
      observer.disconnect();
      frames.dispose();
      geometry.dispose();
      material.dispose();
    },
  };
}
