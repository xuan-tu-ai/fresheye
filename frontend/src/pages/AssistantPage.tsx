import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiError, getInspection, streamChat } from "../api/client";
import type { InspectionOut } from "../api/types";
import { AssistantIcon } from "../components/AssistantBubble";
import { AssistantText } from "../components/AssistantText";
import {
  AlertIcon,
  ArrowRightIcon,
  BackIcon,
  ChevronIcon,
  OfflineIcon,
  RetryIcon,
} from "../components/icons";
import { Alert, Button, LEVEL_NAMES, LevelMark, Notice, Spinner, StatePanel } from "../components/ui";
import { visibleMessages } from "../lib/conversation";

interface Turn {
  role: "user" | "assistant";
  text: string;
}

const SUGGESTIONS = [
  "Vì sao có kết quả này?",
  "Nên bảo quản cá thế nào?",
  "Cá này để được bao lâu?",
];

/** Pinned strip that keeps the result in view; it never names a level unless the app concluded one. */
function ResultStrip({ inspection }: { inspection: InspectionOut }) {
  const decision = inspection.decision;
  const level = decision?.action === "ANSWER" ? decision.label : null;
  const outcome =
    level !== null
      ? LEVEL_NAMES[level]
      : decision?.action === "ABSTAIN"
        ? "Chưa thể kết luận"
        : "Cần chụp thêm ảnh";
  const photo = inspection.images.at(-1);

  return (
    <Link
      to={`/ket-qua/${inspection.id}`}
      className="mx-4 flex items-center gap-3 rounded-card border-[1.5px] border-navy bg-paper p-2.5 pr-3"
    >
      {photo && (
        <img
          src={photo.image_url}
          alt=""
          className="size-12 flex-none rounded-control border border-rule object-cover"
        />
      )}
      <span className="flex min-w-0 flex-1 items-center gap-2 font-semibold leading-tight">
        <LevelMark level={level} />
        {outcome}
      </span>
      <span className="flex flex-none items-center gap-0.5 text-small font-semibold">
        Xem kết quả
        <ChevronIcon width={18} height={18} />
      </span>
    </Link>
  );
}

function Message({ turn }: { turn: Turn }) {
  if (turn.role === "user") {
    return (
      <li className="ml-12 justify-self-end rounded-card rounded-br-md bg-navy px-4 py-2.5 text-white">
        {turn.text}
      </li>
    );
  }
  return (
    <li className="grid grid-cols-[32px_1fr] items-start gap-2">
      <AssistantIcon className="size-8" />
      <div className="mr-6 justify-self-start rounded-card rounded-tl-md border-[1.5px] border-navy bg-paper px-4 py-2.5">
        {turn.text ? (
          <AssistantText text={turn.text} />
        ) : (
          <span className="flex h-6 items-center gap-1.5" aria-label="Trợ lý đang viết">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="size-2 animate-bounce rounded-full bg-navy"
                style={{ animationDelay: `${dot * 150}ms` }}
              />
            ))}
          </span>
        )}
      </div>
    </li>
  );
}

/** Conversation with the assistant about one inspection. */
export function AssistantPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const location = useLocation();
  const question = (location.state as { question?: string } | null)?.question;

  const [inspection, setInspection] = useState<InspectionOut | null>(null);
  const [problem, setProblem] = useState<"missing" | "offline" | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [unanswered, setUnanswered] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const sentStarter = useRef(false);

  useEffect(() => {
    // A superseded request must not overwrite the thread once a question has been sent.
    let current = true;
    setProblem(null);
    getInspection(id).then(
      (loaded) => {
        if (!current) return;
        setInspection(loaded);
        setTurns(
          visibleMessages(loaded.messages).map((m) => ({
            role: m.role === "user" ? "user" : "assistant",
            text: m.content,
          })),
        );
      },
      (error) =>
        current &&
        setProblem(error instanceof ApiError && error.status === 404 ? "missing" : "offline"),
    );
    return () => {
      current = false;
    };
  }, [id, attempt]);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [turns, unanswered]);

  /** `repeat` resends a question whose bubble is already on screen. */
  async function send(text: string, repeat = false) {
    const message = text.trim();
    if (!message || busy) return;
    setBusy(true);
    setUnanswered(null);
    setDraft("");
    setTurns((all) => [
      ...all,
      ...(repeat ? [] : [{ role: "user" as const, text: message }]),
      { role: "assistant", text: "" },
    ]);
    let received = false;
    try {
      await streamChat(id, { kind: "user", message }, (chunk) => {
        received = true;
        setTurns((all) => [
          ...all.slice(0, -1),
          { role: "assistant", text: all[all.length - 1].text + chunk },
        ]);
      });
      if (!received) throw new Error("The assistant sent no text");
    } catch {
      // Drop the empty or cut-off reply and keep the question so it can be sent again.
      setTurns((all) => (received ? all : all.slice(0, -1)));
      setUnanswered(message);
    } finally {
      setBusy(false);
    }
  }

  // A starter question tapped on the result screen is sent once, then removed from the history entry.
  useEffect(() => {
    if (!inspection || !question || sentStarter.current) return;
    sentStarter.current = true;
    navigate(location.pathname, { replace: true });
    void send(question);
    // `send` is recreated every render; this effect must run only when the inspection arrives.
  }, [inspection, question]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  return (
    <main className="mx-auto flex h-dvh max-w-[390px] flex-col">
      <header className="grid grid-cols-[44px_1fr_44px] items-center gap-2 px-4 py-3">
        <Link
          to={`/ket-qua/${id}`}
          aria-label="Quay lại kết quả"
          className="grid size-11 place-items-center rounded-full border-[1.5px] border-navy"
        >
          <BackIcon />
        </Link>
        <h1 className="text-center font-serif text-title font-bold">Trợ lý FreshEye</h1>
      </header>

      {!inspection && !problem && (
        <StatePanel icon={<Spinner className="size-8" />} title="Đang mở cuộc trò chuyện">
          Bạn chờ một chút nhé.
        </StatePanel>
      )}
      {!inspection && problem === "offline" && (
        <div className="px-4">
          <StatePanel
            icon={<OfflineIcon />}
            title="Chưa kết nối được"
            action={
              <Button icon={<RetryIcon />} onClick={() => setAttempt((n) => n + 1)}>
                Thử lại
              </Button>
            }
          >
            FreshEye chưa mở được cuộc trò chuyện. Hãy kiểm tra mạng rồi thử lại.
          </StatePanel>
        </div>
      )}
      {!inspection && problem === "missing" && (
        <div className="px-4">
          <StatePanel
            icon={<AlertIcon />}
            title="Không tìm thấy lượt này"
            action={
              <Link
                to="/"
                className="flex min-h-[52px] items-center justify-center rounded-control border-[1.5px] border-navy bg-navy px-4 font-semibold text-white active:opacity-80"
              >
                Về màn kiểm tra
              </Link>
            }
          >
            Lượt kiểm tra này không còn trong lịch sử.
          </StatePanel>
        </div>
      )}

      {inspection && (
        <>
          <ResultStrip inspection={inspection} />

          <div className="mt-3 min-h-0 flex-1 overflow-y-auto border-y border-rule px-4 py-4">
            {turns.length === 0 && (
              <div className="grid gap-3 py-2">
                <p className="text-center text-ink-soft">
                  Bạn muốn hỏi gì về con cá này? Hãy chọn một câu hoặc tự gõ câu hỏi ở dưới.
                </p>
                <ul className="grid gap-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <li key={suggestion}>
                      <button
                        type="button"
                        onClick={() => send(suggestion)}
                        className="flex min-h-12 w-full items-center justify-between gap-2 rounded-control border-[1.5px] border-navy bg-paper px-3 text-left font-medium active:opacity-80"
                      >
                        {suggestion}
                        <ChevronIcon className="flex-none" />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <ul className="grid gap-3" aria-live="polite">
              {turns.map((turn, index) => (
                <Message key={index} turn={turn} />
              ))}
            </ul>
            {unanswered && (
              <div className="mt-3 grid gap-2">
                <Alert>Trợ lý chưa trả lời được câu này. Kết quả kiểm tra vẫn dùng được.</Alert>
                <Button variant="secondary" icon={<RetryIcon />} onClick={() => send(unanswered, true)}>
                  Gửi lại câu hỏi
                </Button>
              </div>
            )}
            <div ref={end} />
          </div>

          <section className="grid gap-2.5 px-4 pb-[calc(10px+env(safe-area-inset-bottom))] pt-3">
            <form
              onSubmit={handleSubmit}
              // The text field has no outline of its own; the whole pill shows the focus ring instead.
              className="grid grid-cols-[1fr_44px] items-center gap-1 rounded-full border-[1.5px] border-navy bg-paper py-1 pl-4 pr-1 has-[input:focus-visible]:outline-3 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-coral-ink"
            >
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Hỏi về con cá này…"
                aria-label="Câu hỏi cho trợ lý"
                maxLength={500}
                enterKeyHint="send"
                className="h-11 min-w-0 bg-transparent placeholder:text-ink-muted focus:outline-none"
              />
              <button
                type="submit"
                aria-label="Gửi"
                disabled={busy || !draft.trim()}
                className="grid size-11 place-items-center rounded-full bg-navy text-white disabled:opacity-40"
              >
                <ArrowRightIcon />
              </button>
            </form>
            <Notice className="text-caption" />
          </section>
        </>
      )}
    </main>
  );
}
