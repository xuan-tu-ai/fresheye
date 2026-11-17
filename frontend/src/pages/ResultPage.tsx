import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { ApiError, getInspection, streamChat } from "../api/client";
import type { DecisionOut, ImageOut, InspectionOut, Level } from "../api/types";
import { AssistantBubble } from "../components/AssistantBubble";
import { AssistantText } from "../components/AssistantText";
import {
  AlertIcon,
  BackIcon,
  CameraIcon,
  ChevronIcon,
  OfflineIcon,
  RetryIcon,
} from "../components/icons";
import {
  Button,
  Card,
  Label,
  LEVEL_NAMES,
  LevelMark,
  Spinner,
  StatePanel,
  Tag,
} from "../components/ui";
import { storedExplanation } from "../lib/conversation";
import { formatPercent } from "../lib/format";
import { AbstainView } from "./AbstainView";
import { AskMoreView } from "./AskMoreView";

const LEVELS: Level[] = [0, 1, 2];

const LEVEL_BAR: Record<Level, string> = {
  0: "bg-level-very-fresh",
  1: "bg-level-fresh",
  2: "bg-level-not-fresh",
};

const LEVEL_TEXT: Record<Level, string> = {
  0: "text-level-very-fresh",
  1: "text-level-fresh",
  2: "text-level-not-fresh",
};

/** Eye crop with the attention overlay at one fixed strength; testers did not understand a slider. */
function EyePhoto({ images }: { images: ImageOut[] }) {
  const [index, setIndex] = useState(images.length - 1);
  const image = images[index];

  return (
    <section className="grid gap-3">
      <div className="relative aspect-square overflow-hidden rounded-card border-[1.5px] border-navy bg-navy">
        <img src={image.image_url} alt="Ảnh mắt cá đã kiểm tra" className="size-full object-cover" />
        <img
          src={image.cam_url}
          alt=""
          // The backend's heat map is a coarse grid; the blur turns its blocks into soft regions.
          className="absolute inset-0 size-full scale-110 object-cover opacity-60 blur-md"
        />
        <Tag className="absolute left-3 top-3 gap-2">
          <span className="size-2 rounded-full bg-coral" aria-hidden="true" />
          Vùng mô hình chú ý
        </Tag>
      </div>

      {images.length > 1 && (
        <ul className="flex gap-2">
          {images.map((item, i) => (
            <li key={item.seq}>
              <button
                type="button"
                aria-label={`Xem ảnh ${item.seq}`}
                aria-pressed={i === index}
                onClick={() => setIndex(i)}
                className={`block size-14 overflow-hidden rounded-control border-[1.5px] border-navy ${
                  i === index ? "outline-3 outline-offset-2 outline-coral-ink" : "opacity-70"
                }`}
              >
                <img src={item.image_url} alt="" className="size-full object-cover" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function VerdictCard({ decision, level }: { decision: DecisionOut; level: Level }) {
  return (
    <Card>
      <Label>Mức độ tươi</Label>
      <p className="mt-2 flex items-center gap-3 font-serif text-[2.75rem] leading-tight font-bold">
        <LevelMark level={level} className="size-5 border-[3px]" />
        {LEVEL_NAMES[level]}
      </p>
      <p className="mt-2 flex items-baseline justify-between gap-3 border-b border-rule pb-4">
        <span className="text-ink-soft">Độ tin cậy</span>
        <span className="text-numeral leading-none font-bold">{formatPercent(decision.conf)}</span>
      </p>

      <ul className="mt-3 grid gap-1">
        {LEVELS.map((item) => (
          <li
            key={item}
            className={`rounded-control px-3 py-2 ${item === level ? "bg-seaglass/60" : ""}`}
          >
            <div className="flex items-center justify-between gap-3">
              <span
                className={`flex items-center gap-2 ${item === level ? "font-semibold" : "text-ink-soft"}`}
              >
                <LevelMark level={item} />
                {LEVEL_NAMES[item]}
              </span>
              <span className={`font-semibold ${LEVEL_TEXT[item]}`}>
                {formatPercent(decision.probs[item])}
              </span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-navy/10">
              <div
                className={`h-full rounded-full ${LEVEL_BAR[item]}`}
                style={{ width: `${Math.max(decision.probs[item] * 100, 1.5)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Starter questions under the explanation; tapping one opens the conversation with it. */
const FOLLOW_UPS = ["Vì sao có kết quả này?", "Nên bảo quản cá thế nào?"];

/** The assistant's explanation: stored text if the inspection already has one, else streamed now. */
function ExplanationCard({ inspection }: { inspection: InspectionOut }) {
  const stored = storedExplanation(inspection.messages);
  const [text, setText] = useState(stored ?? "");
  const [failed, setFailed] = useState(false);
  const requested = useRef(false);

  function ask() {
    setText("");
    setFailed(false);
    streamChat(inspection.id, { kind: "explain" }, (chunk) => setText((t) => t + chunk)).catch(() =>
      setFailed(true),
    );
  }

  useEffect(() => {
    // The ref keeps React's development double-run from asking the assistant twice.
    if (stored || requested.current) return;
    requested.current = true;
    ask();
  }, [inspection.id, stored]);

  return (
    <Card className="border-l-[6px] border-l-coral">
      <Label>Trợ lý FreshEye</Label>
      {failed && !text ? (
        <div className="mt-2 grid gap-3">
          <p>Trợ lý chưa trả lời được. Kết quả ở trên vẫn dùng được.</p>
          <Button variant="secondary" icon={<RetryIcon />} onClick={ask}>
            Hỏi lại trợ lý
          </Button>
        </div>
      ) : (
        <div className="mt-2" aria-live="polite">
          {text ? (
            <AssistantText text={text} />
          ) : (
            <p className="animate-pulse text-ink-soft">Trợ lý đang viết…</p>
          )}
        </div>
      )}
      <div className="mt-4 border-t border-rule pt-4">
        <p className="text-small font-medium text-ink-soft">Bạn có thể hỏi thêm:</p>
        <ul className="mt-2 grid gap-2">
          {FOLLOW_UPS.map((question) => (
            <li key={question}>
              <Link
                to={`/tro-ly/${inspection.id}`}
                state={{ question }}
                className="flex min-h-12 items-center justify-between gap-2 rounded-control border-[1.5px] border-navy bg-seaglass/60 px-3 font-medium active:opacity-80"
              >
                {question}
                <ChevronIcon className="flex-none" />
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

/** Result of one inspection. Only an ANSWER shows a freshness level; ASK_MORE and ABSTAIN have their own views. */
export function ResultPage() {
  const id = Number(useParams().id);
  // Set by the history list so the back button returns there.
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [inspection, setInspection] = useState<InspectionOut | null>(null);
  const [problem, setProblem] = useState<"missing" | "offline" | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setProblem(null);
    getInspection(id).then(setInspection, (error) =>
      setProblem(error instanceof ApiError && error.status === 404 ? "missing" : "offline"),
    );
  }, [id, attempt]);

  const decision = inspection?.decision;
  const answered =
    decision?.action === "ANSWER" && decision.label !== null && inspection!.images.length > 0;

  return (
    <div className="grid gap-5">
      <header className="grid grid-cols-[44px_1fr_auto] items-center gap-2">
        <Link
          to={from ?? "/"}
          aria-label={from ? "Quay lại lịch sử" : "Về màn kiểm tra"}
          className="grid size-11 place-items-center rounded-full border-[1.5px] border-navy"
        >
          <BackIcon />
        </Link>
        <h1 className="text-center font-serif text-title font-bold">Kết quả kiểm tra</h1>
        <span className="flex min-w-11 justify-end">
          {decision && <Tag>{decision.n_images} ảnh</Tag>}
        </span>
      </header>

      {!inspection && !problem && (
        <StatePanel icon={<Spinner className="size-8" />} title="Đang tải kết quả">
          Bạn chờ một chút nhé.
        </StatePanel>
      )}
      {!inspection && problem === "offline" && (
        <StatePanel
          icon={<OfflineIcon />}
          title="Chưa kết nối được"
          action={
            <Button icon={<RetryIcon />} onClick={() => setAttempt((n) => n + 1)}>
              Thử lại
            </Button>
          }
        >
          FreshEye chưa tải được kết quả. Hãy kiểm tra mạng rồi thử lại.
        </StatePanel>
      )}
      {!inspection && problem === "missing" && (
        <StatePanel
          icon={<AlertIcon />}
          title="Không tìm thấy lượt này"
          action={
            <Link
              to="/"
              className="flex min-h-[52px] items-center justify-center gap-2.5 rounded-control border-[1.5px] border-navy bg-navy px-4 font-semibold text-white active:opacity-80"
            >
              <CameraIcon />
              Về màn kiểm tra
            </Link>
          }
        >
          Lượt kiểm tra này không còn trong lịch sử.
        </StatePanel>
      )}

      {inspection && decision && answered && (
        <>
          <EyePhoto images={inspection.images} />
          <VerdictCard decision={decision} level={decision.label as Level} />
          <ExplanationCard inspection={inspection} />
          <Link
            to="/"
            className="flex min-h-[52px] items-center justify-center gap-2.5 rounded-control border-[1.5px] border-navy bg-navy px-4 font-semibold text-white active:opacity-80"
          >
            <CameraIcon />
            Kiểm tra con cá khác
          </Link>
          <AssistantBubble inspectionId={inspection.id} />
        </>
      )}

      {inspection && decision?.action === "ASK_MORE" && inspection.images.length > 0 && (
        <AskMoreView inspection={inspection} />
      )}

      {inspection && decision?.action === "ABSTAIN" && <AbstainView inspection={inspection} />}

      {inspection && (!decision || (!answered && inspection.images.length === 0)) && (
        <p className="text-center text-ink-soft">Lượt này chưa có ảnh nào để kết luận.</p>
      )}
    </div>
  );
}
