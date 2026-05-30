/**
 * Format a date string to Beijing time (Asia/Shanghai, UTC+8).
 * Works regardless of server/client timezone settings.
 *
 * Backend stores all timestamps as UTC (datetime.utcnow / func.now()),
 * but returns them WITHOUT timezone suffix (e.g. "2026-05-29T13:44:27.123456").
 * JavaScript treats such strings as local time, which is wrong.
 * We fix this by appending "Z" to mark them as UTC before parsing.
 */

const BJ_TIMEZONE = "Asia/Shanghai";

/** Ensure a date string is treated as UTC by appending 'Z' if no timezone info */
function ensureUTC(dateStr: string): string {
  // Already has timezone info (Z, +08:00, etc.)
  if (/[Zz]$/.test(dateStr) || /[+-]\d{2}:\d{2}$/.test(dateStr)) {
    return dateStr;
  }
  return dateStr + "Z";
}

export function formatTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(ensureUTC(dateStr));
    return d.toLocaleString("zh-CN", {
      timeZone: BJ_TIMEZONE,
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return String(dateStr);
  }
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(ensureUTC(dateStr));
    return d.toLocaleString("zh-CN", {
      timeZone: BJ_TIMEZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return String(dateStr);
  }
}

export function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "";
  try {
    const d = new Date(ensureUTC(dateStr));
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "刚刚";
    if (diffMins < 60) return `${diffMins}分钟前`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24) return `${diffHrs}小时前`;
    const diffDays = Math.floor(diffHrs / 24);
    if (diffDays < 7) return `${diffDays}天前`;
    return d.toLocaleDateString("zh-CN", { timeZone: BJ_TIMEZONE, month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}
