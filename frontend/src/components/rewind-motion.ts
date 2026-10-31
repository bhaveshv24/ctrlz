export const REWIND_DURATION = 4.2;
export const REWIND_REVEAL = 0.74;
const smooth = (a: number, b: number, value: number) => {
  const x = Math.max(0, Math.min(1, (value - a) / (b - a)));
  return x * x * (3 - 2 * x);
};
/** Spin, eclipse, then reveal. Integral rotations return the disc to a seamless rest. */
export function rewindMotion(progress: number) {
  const p = Math.max(0, Math.min(1, progress));
  const spin = smooth(0, 1, p);
  return {
    turn: spin * Math.PI * 4,
    bank: Math.sin(p * Math.PI) * 0.42,
    strength: Math.sin(p * Math.PI),
    shadow: smooth(0.38, 0.68, p) * (1 - smooth(REWIND_REVEAL, 1, p)),
    reveal: p >= REWIND_REVEAL,
  };
}
