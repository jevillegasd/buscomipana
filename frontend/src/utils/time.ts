export function formatRelativeTime(iso: string): string {
  const diffMin = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diffMin < 1) return "Justo ahora";
  if (diffMin < 60) return `Hace ${diffMin} min${diffMin === 1 ? "" : "s"}`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `Hace ${diffHr} hora${diffHr === 1 ? "" : "s"}`;
  const diffDay = Math.floor(diffHr / 24);
  return `Hace ${diffDay} día${diffDay === 1 ? "" : "s"}`;
}
