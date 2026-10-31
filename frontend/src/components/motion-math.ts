/** Frame-rate-independent damping and the shortest rotational path. */
export const damping = (dt: number, response = 7) => 1 - Math.exp(-Math.max(0, Math.min(dt, 0.05)) * response);
export const angleDelta = (from: number, to: number) => Math.atan2(Math.sin(to - from), Math.cos(to - from));
export function pointerDepth(x: number, y: number) {
  const clamp = (value: number) => Math.max(-1, Math.min(1, value));
  return { x: -clamp(y) * 1.4, y: clamp(x) * 1.8 };
}
