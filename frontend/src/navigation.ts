export function routeValue() {
  const value = window.location.hash.slice(1);
  return [
    "overview",
    "incidents",
    "projects",
    "continuity",
    "demo",
    "evidence",
    "settings",
  ].includes(value) || value.startsWith("incident/")
    ? value
    : "overview";
}
export const navigate = (route: string) => {
  window.location.hash = route;
};
