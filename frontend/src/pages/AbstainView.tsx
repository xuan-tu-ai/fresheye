import { Link } from "react-router-dom";

import type { InspectionOut } from "../api/types";
import { AssistantBubble } from "../components/AssistantBubble";
import { CameraIcon } from "../components/icons";
import { PhotoStrip } from "../components/PhotoStrip";
import { Card, Label, LevelMark } from "../components/ui";

/** What a buyer can check by hand when the app declines to judge. */
const SENSORY_CHECKS: [string, string][] = [
  ["Mắt", "trong, lồi, không đục."],
  ["Mùi", "tanh nhẹ, không hôi."],
  ["Mang", "đỏ tươi, không thâm."],
  ["Thịt", "ấn vào đàn hồi lại ngay."],
];

/**
 * "Chưa thể kết luận": the app declines to judge this fish.
 * Says so in plain words, never names a freshness level and shows no model figures.
 */
export function AbstainView({ inspection }: { inspection: InspectionOut }) {
  return (
    <>
      <PhotoStrip images={inspection.images} />

      <Card>
        <Label>Kết quả</Label>
        <h2 className="mt-2 flex items-center gap-3 font-serif text-[1.75rem] leading-tight font-bold">
          <LevelMark level={null} className="w-4" />
          Chưa thể kết luận
        </h2>
        <p className="mt-3">
          FreshEye không đủ chắc chắn để đánh giá con cá này, nên không đưa ra mức độ tươi. Bạn hãy tự
          kiểm tra theo gợi ý bên dưới.
        </p>
      </Card>

      <Link
        to="/"
        className="flex min-h-[52px] items-center justify-center gap-2.5 rounded-control border-[1.5px] border-navy bg-navy px-4 font-semibold text-white active:opacity-80"
      >
        <CameraIcon />
        Bắt đầu lượt kiểm tra mới
      </Link>

      <Card>
        <Label className="flex items-center gap-2 border-b border-rule pb-3">
          <span className="size-2 rounded-full bg-coral" aria-hidden="true" />
          Hãy kiểm tra bằng cảm quan
        </Label>
        <ul className="mt-2 divide-y divide-rule">
          {SENSORY_CHECKS.map(([part, sign]) => (
            <li key={part} className="grid grid-cols-[4rem_1fr] gap-3 py-3">
              <span className="font-semibold">{part}</span>
              <span>{sign}</span>
            </li>
          ))}
        </ul>
      </Card>

      <AssistantBubble inspectionId={inspection.id} />
    </>
  );
}
