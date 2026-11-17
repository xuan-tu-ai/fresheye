import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listInspections } from "../api/client";
import type { InspectionOut } from "../api/types";
import { EyeIllustration } from "../components/EyeIllustration";
import { CameraIcon, ChevronIcon, ImageIcon } from "../components/icons";
import { usePhotoPicker } from "../components/PhotoPicker";
import { Alert, Button, Card, Label, LEVEL_NAMES, LevelMark, Logo } from "../components/ui";
import { formatWhen } from "../lib/format";

const TIPS = [
  "Đưa máy lại gần, mắt cá chiếm phần lớn khung hình.",
  "Chụp nơi đủ sáng, tránh bóng đổ và phản chiếu.",
  "Giữ máy chắc tay, ảnh không bị nhoè.",
];

const RECENT_COUNT = 2;

/** Short result text for a past inspection; never names a level unless the app concluded one. */
function outcome(inspection: InspectionOut): string {
  const decision = inspection.decision;
  if (decision?.action === "ANSWER" && decision.label !== null) return LEVEL_NAMES[decision.label];
  if (decision?.action === "ABSTAIN") return "Từ chối kết luận";
  return "Cần chụp thêm";
}

function RecentCard({ inspection }: { inspection: InspectionOut }) {
  const decision = inspection.decision;
  const level = decision?.action === "ANSWER" ? decision.label : null;
  return (
    <li className="flex items-center gap-3 rounded-card border-[1.5px] border-navy bg-paper p-3">
      <img
        src={inspection.images[0].image_url}
        alt=""
        className="size-12 flex-none rounded-control border border-rule object-cover"
      />
      <p className="flex min-w-0 flex-1 items-center gap-2 font-semibold leading-tight">
        <LevelMark level={level} />
        {outcome(inspection)}
      </p>
      <p className="flex-none text-small text-ink-muted">{formatWhen(inspection.created_at)}</p>
    </li>
  );
}

/** Start screen of the "Kiểm tra" tab: take or pick a photo, with tips and the latest inspections. */
export function InspectPage() {
  const picker = usePhotoPicker();
  const [recent, setRecent] = useState<InspectionOut[]>([]);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    // Inspections with no photo yet are not results; a failed request means the server is unreachable.
    listInspections(20).then(
      (all) =>
        setRecent(all.filter((i) => i.images.length > 0 && i.decision).slice(0, RECENT_COUNT)),
      () => setOffline(true),
    );
  }, []);

  return (
    <div className="grid gap-6">
      <header>
        <Logo />
      </header>

      <section className="text-center">
        <EyeIllustration />
        <h1 className="mt-4 font-serif text-[2.25rem] leading-[1.1] font-bold">Cá có tươi không?</h1>
        <p className="mt-2 text-ink-soft">Chụp cận cảnh mắt cá, FreshEye sẽ đánh giá độ tươi.</p>
      </section>

      <section className="grid gap-3">
        {offline && (
          <Alert>Chưa kết nối được máy chủ. Bạn hãy kiểm tra mạng trước khi chụp ảnh.</Alert>
        )}
        <Button icon={<CameraIcon />} onClick={picker.openCamera}>
          Chụp ảnh mắt cá
        </Button>
        <Button
          variant="secondary"
          icon={<ImageIcon />}
          onClick={picker.openLibrary}
        >
          Chọn ảnh từ thư viện
        </Button>
        {picker.inputs}
      </section>

      <Card>
        <Label className="flex items-center gap-2 border-b border-rule pb-3">
          <span className="size-2 rounded-full bg-coral" aria-hidden="true" />
          Để ảnh rõ nhất
        </Label>
        <ol className="mt-4 grid gap-3">
          {TIPS.map((tip, index) => (
            <li key={tip} className="grid grid-cols-[auto_1fr] gap-3">
              <span
                aria-hidden="true"
                className="grid size-6 place-items-center rounded-full border-[1.5px] border-navy text-caption font-semibold"
              >
                {index + 1}
              </span>
              {tip}
            </li>
          ))}
        </ol>
      </Card>

      {recent.length > 0 && (
        <section>
          <div className="flex items-center justify-between">
            <Label>Lượt kiểm tra gần đây</Label>
            <Link
              to="/lich-su"
              className="-mr-1 flex min-h-11 items-center gap-0.5 text-small font-semibold"
            >
              Tất cả
              <ChevronIcon width={18} height={18} />
            </Link>
          </div>
          <ul className="grid gap-2.5">
            {recent.map((inspection) => (
              <RecentCard key={inspection.id} inspection={inspection} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
