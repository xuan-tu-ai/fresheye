import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { closeInspection, getHealth } from "../api/client";
import type { InspectionOut } from "../api/types";
import { AssistantBubble } from "../components/AssistantBubble";
import { CameraIcon, PlusIcon } from "../components/icons";
import { usePhotoPicker } from "../components/PhotoPicker";
import { PhotoStrip } from "../components/PhotoStrip";
import { Alert, Button, Card, Label, LevelMark } from "../components/ui";

const TIPS = [
  "Chụp từ một góc khác của mắt cá.",
  "Chuyển sang nơi sáng hơn, tránh bóng đổ và phản chiếu.",
  "Đưa máy lại gần hơn và giữ chắc tay.",
];

/**
 * "Cần chụp thêm ảnh": the photos so far were not enough for a conclusion.
 * Says so in plain words, never names a freshness level and shows no model figures.
 */
export function AskMoreView({ inspection }: { inspection: InspectionOut }) {
  const navigate = useNavigate();
  const count = inspection.images.length;
  const open = inspection.status === "open";
  const picker = usePhotoPicker({ inspectionId: inspection.id, imageCount: count });
  const [maxImages, setMaxImages] = useState<number | null>(null);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth().then(
      (health) => setMaxImages(health.policy.max_images),
      () => setMaxImages(null),
    );
  }, []);

  async function handleStop() {
    setStopping(true);
    setError(null);
    try {
      await closeInspection(inspection.id);
      navigate("/");
    } catch {
      setError("Chưa dừng được lượt này. Hãy thử lại.");
      setStopping(false);
    }
  }

  // Empty slots show how many photos are still allowed; without the limit, only the next one.
  const emptySlots = open ? Math.max((maxImages ?? count + 1) - count, 0) : 0;

  return (
    <>
      <PhotoStrip images={inspection.images}>
        {Array.from({ length: emptySlots }, (_, i) => {
          const seq = count + i + 1;
          return i === 0 ? (
            <li key={seq}>
              <button
                type="button"
                onClick={picker.openCamera}
                className="grid aspect-square w-full place-content-center justify-items-center gap-1 rounded-control border-[1.5px] border-dashed border-navy bg-paper/60 font-semibold active:opacity-80"
              >
                <PlusIcon />
                Ảnh {seq}
              </button>
            </li>
          ) : (
            <li
              key={seq}
              className="grid aspect-square place-content-center rounded-control border-[1.5px] border-dashed border-ink-muted text-ink-muted"
            >
              Ảnh {seq}
            </li>
          );
        })}
      </PhotoStrip>

      <Card>
        <Label>Kết quả</Label>
        <h2 className="mt-2 flex items-center gap-3 font-serif text-[1.75rem] leading-tight font-bold">
          <LevelMark level={null} className="w-4" />
          {open ? "Cần chụp thêm ảnh" : "Chưa có kết luận"}
        </h2>
        <p className="mt-3">
          {open
            ? "FreshEye chưa đủ chắc chắn để kết luận. Hãy chụp thêm một ảnh mắt của chính con cá này."
            : "Lượt kiểm tra này đã dừng trước khi FreshEye đủ chắc chắn để kết luận."}
        </p>
      </Card>

      {open ? (
        <section className="grid justify-items-center gap-1">
          {error && <Alert className="mb-2 w-full">{error}</Alert>}
          <Button icon={<CameraIcon />} disabled={stopping} onClick={picker.openCamera}>
            Chụp thêm ảnh
          </Button>
          {/* Text links stay narrow and centred so they never sit under the floating assistant mark. */}
          <button
            type="button"
            disabled={stopping}
            onClick={picker.openLibrary}
            className="mt-2 min-h-11 px-2 font-semibold underline underline-offset-4 disabled:opacity-50"
          >
            Chọn ảnh từ thư viện
          </button>
          <button
            type="button"
            disabled={stopping}
            onClick={handleStop}
            className="min-h-11 px-2 font-medium text-ink-soft underline underline-offset-4 disabled:opacity-50"
          >
            Dừng lượt kiểm tra này
          </button>
          {picker.inputs}
        </section>
      ) : (
        <Link
          to="/"
          className="flex min-h-[52px] items-center justify-center gap-2.5 rounded-control border-[1.5px] border-navy bg-navy px-4 font-semibold text-white active:opacity-80"
        >
          <CameraIcon />
          Kiểm tra con cá khác
        </Link>
      )}

      {open && (
        <Card>
          <Label className="flex items-center gap-2 border-b border-rule pb-3">
            <span className="size-2 rounded-full bg-coral" aria-hidden="true" />
            Gợi ý cho ảnh tiếp theo
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
      )}

      <AssistantBubble inspectionId={inspection.id} />
    </>
  );
}
