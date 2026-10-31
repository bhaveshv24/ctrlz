/** Adjacent text chapters never share a visible frame, including while scrolling back. */
export function chapterTransition(position: number, index: number) {
  const distance = position - index;
  const strength = Math.max(0, Math.min(1, (0.48 - Math.abs(distance)) / 0.26));
  const opacity = strength * strength * (3 - 2 * strength);
  return { opacity, visible: opacity > 0, offset: -distance * 28 };
}
