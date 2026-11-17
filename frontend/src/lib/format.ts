// Vietnamese display formatting shared by every screen.

const TIME = new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false });
const DAY = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit" });

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** "10:42 hôm nay", "Hôm qua", or "03/10" for anything older. Input is an ISO timestamp. */
export function formatWhen(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const days = Math.round((startOfDay(now) - startOfDay(date)) / 86_400_000);
  if (days <= 0) return `${TIME.format(date)} hôm nay`;
  if (days === 1) return "Hôm qua";
  return DAY.format(date);
}

const FULL_DAY = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });

/** Heading for a day in a list: "Hôm nay", "Hôm qua", or "03/10/2026". */
export function formatDay(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const days = Math.round((startOfDay(now) - startOfDay(date)) / 86_400_000);
  if (days <= 0) return "Hôm nay";
  if (days === 1) return "Hôm qua";
  return FULL_DAY.format(date);
}

/** Clock time of a timestamp in the reader's zone, e.g. "10:42". */
export function formatTime(iso: string): string {
  return TIME.format(new Date(iso));
}

/** 0.96 -> "96%". Anything short of certain stops at 99%, so 0.9994 never reads as "100%". */
export function formatPercent(value: number): string {
  const percent = Math.round(value * 100);
  return `${value < 1 ? Math.min(percent, 99) : percent}%`;
}

/** 0.35 -> "0,35" (Vietnamese decimal comma). */
export function formatDecimal(value: number, digits = 2): string {
  return value.toFixed(digits).replace(".", ",");
}
