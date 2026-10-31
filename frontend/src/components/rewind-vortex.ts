import * as T from "three";

export function rewindVortex(scene: T.Scene) {
  const count = 16000,
    geometry = new T.BufferGeometry(),
    coordinates = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    coordinates[i * 3] = i / count;
    coordinates[i * 3 + 1] = Math.random();
    coordinates[i * 3 + 2] = Math.random();
  }
  geometry.setAttribute("position", new T.BufferAttribute(coordinates, 3));
  const material = new T.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: T.AdditiveBlending,
    uniforms: {
      phase: { value: 0 },
      strength: { value: 0 },
      ratio: { value: 1 },
    },
    vertexShader: `uniform float phase,ratio;varying float light;
  void main(){
    float h=position.x,angle=floor(position.y*5.)*1.25664+(position.z-.5)*.42+h*11.-phase*15.;
    float radius=.14+pow(h,1.65)*3.8;
    radius+=.12*sin(h*39.+position.z*4.);
    vec3 p=vec3(cos(angle)*radius,(h-.5)*7.,sin(angle)*radius);
    p.x+=.28*sin(h*7.+phase*3.);
    vec4 mv=modelViewMatrix*vec4(p,1.);
    gl_Position=projectionMatrix*mv;gl_PointSize=min(7.,ratio*(8.+position.z*9.)/max(1.,-mv.z));
    light=.24+pow(position.z,4.)*.76;
  }`,
    fragmentShader: `uniform float strength;varying float light;
  void main(){float d=length(gl_PointCoord-.5)*2.;float a=exp(-3.8*d*d)*strength*light;
  gl_FragColor=vec4(mix(vec3(.035,.55,.30),vec3(.78,1.,.58),light),a);}`,
  });
  const points = new T.Points(geometry, material);
  points.frustumCulled = false;
  points.visible = false;
  scene.add(points);
  return {
    update(phase: number, strength: number, ratio: number) {
      points.visible = strength > 0;
      material.uniforms.phase.value = phase;
      material.uniforms.strength.value = strength;
      material.uniforms.ratio.value = ratio;
      points.rotation.set(
        0.08,
        -phase * 1.5,
        -0.2 + 0.1 * Math.sin(phase * Math.PI),
      );
      points.position.set(0, 0, 1.1);
    },
    dispose() {
      scene.remove(points);
      geometry.dispose();
      material.dispose();
    },
  };
}
