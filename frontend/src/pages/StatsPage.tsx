import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { getStats } from "../api/client";
import type { Level, StatsOut } from "../api/types";
import { OfflineIcon, RetryIcon, StatsIcon } from "../components/icons";
import {
  Button,
  Card,
  Chip,
  Label,
  LEVEL_NAMES,
  LevelMark,
  Spinner,
  StatePanel,
} from "../components/ui";
import { formatDecimal, formatPercent } from "../lib/format";

const RANGES: { days: number | null; label: string }[] = [
  { days: 7, label: "7 ngày" },
  { days: 30, label: "30 ngày" },
  { days: null, label: "Tất cả" },
];

const OUTCOMES: { action: string; label: string }[] = [
  { action: "ANSWER", label: "Có kết luận" },
  { action: "ASK_MORE", label: "Cần chụp thêm" },
  { action: "ABSTAIN", label: "Từ chối kết luận" },
];

const LEVELS: Level[] = [0, 1, 2];

/** The daily chart never draws more columns than this; older days are left out and said so. */
const MAX_DAYS = 30;

function Tile({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-card border-[1.5px] border-navy bg-paper px-2 py-4 text-center">
      <p className="text-numeral leading-none font-bold">{value}</p>
      <p className="mt-2 text-small text-ink-soft">{label}</p>
    </div>
  );
}

/** One labelled horizontal bar: name on the left, count and share on the right, bar underneath. */
function BarRow({ label, count, total }: { label: ReactNode; count: number; total: number }) {
  const share = total > 0 ? count / total : 0;
  return (
    <li>
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-2 font-medium">{label}</span>
        <span className="flex-none text-small text-ink-soft">
          <span className="text-body font-semibold text-navy">{count}</span> lượt ·{" "}
          {formatPercent(share)}
        </span>
      </div>
      <div className="mt-1.5 h-3 rounded-r-sm bg-navy/10">
        {count > 0 && (
          <div
            className="h-full min-w-1 rounded-r-sm bg-navy"
            style={{ width: `${share * 100}%` }}
          />
        )}
      </div>
    </li>
  );
}

/** Calendar days from `first` to `last` inclusive, as "YYYY-MM-DD" (the keys of `by_day`). */
function daysBetween(first: string, last: string): string[] {
  const days: string[] = [];
  const cursor = new Date(`${first}T00:00:00Z`);
  const end = new Date(`${last}T00:00:00Z`);
  while (cursor <= end) {
    days.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return days;
}

function shortDay(day: string): string {
  return `${day.slice(8, 10)}/${day.slice(5, 7)}`;
}

/** Column chart of inspections per day. Touching or hovering a column names its day and count. */
function DailyChart({ byDay }: { byDay: Record<string, number> }) {
  const keys = Object.keys(byDay).sort();
  const all = keys.length > 0 ? daysBetween(keys[0], keys[keys.length - 1]) : [];
  const days = all.slice(-MAX_DAYS);
  const [picked, setPicked] = useState<string | null>(null);

  if (days.length === 0) return <p className="mt-3 text-ink-soft">Chưa có lượt nào.</p>;

  const peak = Math.max(...days.map((day) => byDay[day] ?? 0), 1);
  const shown = picked && days.includes(picked) ? picked : days[days.length - 1];
  // About six date labels fit under the chart on a phone.
  const labelEvery = Math.ceil(days.length / 6);

  return (
    <>
      <p className="mt-2" aria-live="polite">
        <span className="text-ink-soft">Ngày {shortDay(shown)}: </span>
        <span className="font-semibold">{byDay[shown] ?? 0} lượt</span>
      </p>
      <div
        role="group"
        tabIndex={0}
        aria-label="Biểu đồ lượt kiểm tra theo ngày. Dùng phím mũi tên trái, phải để chọn ngày."
        onKeyDown={(event) => {
          const step = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;
          if (!step) return;
          event.preventDefault();
          const next = Math.min(Math.max(days.indexOf(shown) + step, 0), days.length - 1);
          setPicked(days[next]);
        }}
        className="mt-3 flex h-36 items-end gap-0.5 border-b border-navy"
        onPointerLeave={() => setPicked(null)}
      >
        {days.map((day) => {
          const count = byDay[day] ?? 0;
          return (
            <div
              key={day}
              onPointerEnter={() => setPicked(day)}
              onClick={() => setPicked(day)}
              className="flex h-full min-w-0 flex-1 items-end justify-center"
            >
              <div
                className={`w-full max-w-6 rounded-t-sm ${day === shown ? "bg-coral-ink" : "bg-navy"}`}
                style={{ height: count > 0 ? `max(${(count / peak) * 100}%, 3px)` : 0 }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-0.5 text-caption text-ink-soft" aria-hidden="true">
        {days.map((day, index) => (
          <span key={day} className="min-w-0 flex-1 overflow-visible whitespace-nowrap text-center">
            {index % labelEvery === 0 ? shortDay(day) : ""}
          </span>
        ))}
      </div>
      {all.length > days.length && (
        <p className="mt-2 text-small text-ink-soft">Chỉ hiện {MAX_DAYS} ngày gần nhất.</p>
      )}
      <table className="sr-only">
        <caption>Số lượt kiểm tra theo ngày</caption>
        <tbody>
          {days.map((day) => (
            <tr key={day}>
              <th scope="row">{shortDay(day)}</th>
              <td>{byDay[day] ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

/** "Thống kê" tab: totals, outcomes, freshness levels and daily activity for a chosen period. */
export function StatsPage() {
  const [days, setDays] = useState<number | null>(7);
  const [stats, setStats] = useState<StatsOut | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    setStats(null);
    setFailed(false);
    getStats(days).then(
      (loaded) => current && setStats(loaded),
      () => current && setFailed(true),
    );
    return () => {
      current = false;
    };
  }, [days, attempt]);

  // Inspections that never received a photo have no outcome and are left out of every figure here.
  const counted = stats ? OUTCOMES.reduce((sum, o) => sum + (stats.by_action[o.action] ?? 0), 0) : 0;
  const answered = stats?.by_action.ANSWER ?? 0;

  return (
    <div className="grid gap-5">
      <header>
        <h1 className="font-serif text-page-title leading-tight font-bold">Thống kê</h1>
        <p className="mt-1 text-ink-soft">Tổng hợp các lượt kiểm tra.</p>
      </header>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Khoảng thời gian">
        {RANGES.map((range) => (
          <Chip
            key={range.label}
            active={days === range.days}
            className="min-h-11"
            onClick={() => setDays(range.days)}
          >
            {range.label}
          </Chip>
        ))}
      </div>

      {failed && (
        <StatePanel
          icon={<OfflineIcon />}
          title="Chưa kết nối được"
          action={
            <Button icon={<RetryIcon />} onClick={() => setAttempt((n) => n + 1)}>
              Thử lại
            </Button>
          }
        >
          FreshEye chưa tải được thống kê. Hãy kiểm tra mạng rồi thử lại.
        </StatePanel>
      )}

      {!failed && !stats && (
        <StatePanel icon={<Spinner className="size-8" />} title="Đang tải thống kê">
          Bạn chờ một chút nhé.
        </StatePanel>
      )}

      {!failed && stats && counted === 0 && (
        <StatePanel icon={<StatsIcon />} title="Chưa có số liệu">
          Chưa có lượt kiểm tra nào trong khoảng thời gian này.
        </StatePanel>
      )}

      {!failed && stats && counted > 0 && (
        <>
          <div className="grid grid-cols-3 gap-2.5">
            <Tile value={String(counted)} label="Lượt kiểm tra" />
            <Tile value={formatPercent(answered / counted)} label="Có kết luận" />
            <Tile value={formatDecimal(stats.avg_images, 1)} label="Ảnh mỗi lượt" />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <Label>Kết quả các lượt kiểm tra</Label>
              <ul className="mt-4 grid gap-4">
                {OUTCOMES.map((outcome) => (
                  <BarRow
                    key={outcome.action}
                    label={outcome.label}
                    count={stats.by_action[outcome.action] ?? 0}
                    total={counted}
                  />
                ))}
              </ul>
            </Card>

            <Card>
              <Label>Mức độ tươi của các lượt có kết luận</Label>
              {answered > 0 ? (
                <ul className="mt-4 grid gap-4">
                  {LEVELS.map((level) => (
                    <BarRow
                      key={level}
                      label={
                        <>
                          <LevelMark level={level} />
                          {LEVEL_NAMES[level]}
                        </>
                      }
                      count={stats.by_label[String(level)] ?? 0}
                      total={answered}
                    />
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-ink-soft">Chưa có lượt nào có kết luận.</p>
              )}
            </Card>
          </div>

          <Card>
            <Label>Lượt kiểm tra theo ngày</Label>
            <DailyChart byDay={stats.by_day} />
          </Card>
        </>
      )}
    </div>
  );
}
