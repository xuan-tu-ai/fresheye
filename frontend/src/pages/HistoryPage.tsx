import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listInspections } from "../api/client";
import type { Action, InspectionOut } from "../api/types";
import { CameraIcon, ChevronIcon, HistoryIcon, OfflineIcon, RetryIcon } from "../components/icons";
import { Button, Chip, Label, LEVEL_NAMES, LevelMark, Spinner, StatePanel } from "../components/ui";
import { formatDay, formatTime } from "../lib/format";

const PAGE_SIZE = 20;

const FILTERS: { action: Action | null; label: string }[] = [
  { action: null, label: "Tất cả" },
  { action: "ANSWER", label: "Có kết luận" },
  { action: "ASK_MORE", label: "Cần chụp thêm" },
  { action: "ABSTAIN", label: "Từ chối kết luận" },
];

/** Short result text for a past inspection; never names a level unless the app concluded one. */
function outcome(inspection: InspectionOut): string {
  const decision = inspection.decision;
  if (decision?.action === "ANSWER" && decision.label !== null) return LEVEL_NAMES[decision.label];
  if (decision?.action === "ABSTAIN") return "Từ chối kết luận";
  return "Cần chụp thêm ảnh";
}

function HistoryRow({ inspection }: { inspection: InspectionOut }) {
  const decision = inspection.decision;
  const level = decision?.action === "ANSWER" ? decision.label : null;
  return (
    <li>
      <Link
        to={`/ket-qua/${inspection.id}`}
        state={{ from: "/lich-su" }}
        className="flex items-center gap-3 rounded-card border-[1.5px] border-navy bg-paper p-3 active:opacity-80"
      >
        <img
          src={inspection.images[0].image_url}
          alt=""
          className="size-14 flex-none rounded-control border border-rule object-cover"
        />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2 font-serif text-row-title leading-tight font-bold">
            <LevelMark level={level} />
            {outcome(inspection)}
          </span>
          <span className="mt-1 block text-small text-ink-soft">
            {inspection.images.length} ảnh · {formatTime(inspection.created_at)}
          </span>
        </span>
        <ChevronIcon className="flex-none" />
      </Link>
    </li>
  );
}

/** Splits a newest-first list into runs that share a calendar day. */
function groupByDay(inspections: InspectionOut[]): [string, InspectionOut[]][] {
  const groups: [string, InspectionOut[]][] = [];
  for (const inspection of inspections) {
    const day = formatDay(inspection.created_at);
    const last = groups[groups.length - 1];
    if (last && last[0] === day) last[1].push(inspection);
    else groups.push([day, [inspection]]);
  }
  return groups;
}

/** "Lịch sử" tab: past inspections by day, filtered by outcome; a row reopens that inspection. */
export function HistoryPage() {
  const [filter, setFilter] = useState<Action | null>(null);
  const [items, setItems] = useState<InspectionOut[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    setItems(null);
    setFailed(false);
    listInspections(PAGE_SIZE, 0, filter).then(
      (page) => {
        if (!current) return;
        setItems(page);
        setOffset(page.length);
        setHasMore(page.length === PAGE_SIZE);
      },
      () => current && setFailed(true),
    );
    return () => {
      current = false;
    };
  }, [filter, attempt]);

  async function loadMore() {
    setLoadingMore(true);
    try {
      const page = await listInspections(PAGE_SIZE, offset, filter);
      setItems((all) => [...(all ?? []), ...page]);
      setOffset(offset + page.length);
      setHasMore(page.length === PAGE_SIZE);
    } catch {
      setFailed(true);
    } finally {
      setLoadingMore(false);
    }
  }

  // An inspection with no photo yet has nothing to show.
  const shown = (items ?? []).filter((i) => i.images.length > 0 && i.decision);

  return (
    <div className="grid gap-5">
      <header>
        <h1 className="font-serif text-page-title leading-tight font-bold">Lịch sử</h1>
        <p className="mt-1 text-ink-soft">Các lượt kiểm tra bạn đã thực hiện.</p>
      </header>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Lọc theo kết quả">
        {FILTERS.map((option) => (
          <Chip
            key={option.label}
            active={filter === option.action}
            className="min-h-11"
            onClick={() => setFilter(option.action)}
          >
            {option.label}
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
          FreshEye chưa tải được lịch sử. Hãy kiểm tra mạng rồi thử lại.
        </StatePanel>
      )}

      {!failed && items === null && (
        <StatePanel icon={<Spinner className="size-8" />} title="Đang tải lịch sử">
          Bạn chờ một chút nhé.
        </StatePanel>
      )}

      {!failed && items !== null && shown.length === 0 && !hasMore && (
        <StatePanel
          icon={<HistoryIcon />}
          title={filter ? "Không có lượt nào" : "Chưa có lượt kiểm tra nào"}
          action={
            !filter && (
              <Link
                to="/"
                className="flex min-h-[52px] items-center justify-center gap-2.5 rounded-control border-[1.5px] border-navy bg-navy px-4 font-semibold text-white active:opacity-80"
              >
                <CameraIcon />
                Kiểm tra con cá đầu tiên
              </Link>
            )
          }
        >
          {filter
            ? "Chưa có lượt kiểm tra nào thuộc nhóm này."
            : "Sau khi bạn kiểm tra, kết quả sẽ được lưu ở đây."}
        </StatePanel>
      )}

      {!failed &&
        groupByDay(shown).map(([day, group]) => (
          <section key={day}>
            <div className="flex items-baseline justify-between border-b border-rule pb-2">
              <Label>{day}</Label>
              <span className="text-small text-ink-soft">{group.length} lượt</span>
            </div>
            <ul className="mt-3 grid gap-2.5 lg:grid-cols-2">
              {group.map((inspection) => (
                <HistoryRow key={inspection.id} inspection={inspection} />
              ))}
            </ul>
          </section>
        ))}

      {!failed && hasMore && (
        <Button variant="secondary" disabled={loadingMore} onClick={loadMore}>
          {loadingMore ? "Đang tải…" : "Xem thêm"}
        </Button>
      )}
    </div>
  );
}
