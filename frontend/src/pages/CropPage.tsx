import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import Cropper from "react-easy-crop";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError, createInspection, getHealth, uploadImage } from "../api/client";
import {
  ArrowRightIcon,
  CameraIcon,
  CloseIcon,
  ImageIcon,
  MinusIcon,
  PlusIcon,
} from "../components/icons";
import { Alert, Button, Notice, Tag } from "../components/ui";
import { cropToJpeg } from "../lib/crop";
import type { PixelArea } from "../lib/crop";

/** What the previous screen hands over: the photo, and the inspection it belongs to if one is open. */
export interface CropState {
  src: string;
  source: "camera" | "library";
  inspectionId?: number;
  imageCount?: number;
}

const MIN_ZOOM = 1;
const MAX_ZOOM = 4;
const ZOOM_STEP = 0.25;

function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

type Problem = "bad-photo" | "closed" | "offline";

const PROBLEM_TEXT: Record<Problem, string> = {
  "bad-photo": "Ảnh này không dùng được. Hãy chụp hoặc chọn một ảnh khác.",
  closed: "Lượt kiểm tra này đã kết thúc nên không nhận thêm ảnh. Hãy bắt đầu lượt mới.",
  offline: "Chưa gửi được ảnh. Hãy kiểm tra mạng rồi bấm Phân tích lại.",
};

function classify(error: unknown): Problem {
  if (error instanceof ApiError && error.status === 409) return "closed";
  if (error instanceof ApiError && error.status === 422) return "bad-photo";
  // A failed fetch is a TypeError; anything else here comes from decoding or cropping the photo.
  return error instanceof ApiError || error instanceof TypeError ? "offline" : "bad-photo";
}

/** After this long the waiting screen adds a line so the user does not think the app froze. */
const SLOW_AFTER_MS = 8000;

/** Step two of an inspection: frame the fish eye in a square, then send the crop for analysis. */
export function CropPage() {
  const navigate = useNavigate();
  const state = useLocation().state as CropState | null;
  const retakeInput = useRef<HTMLInputElement>(null);
  // Kept across retries so a failed upload does not leave a second empty inspection behind.
  const inspectionId = useRef(state?.inspectionId);

  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(MIN_ZOOM);
  const [area, setArea] = useState<PixelArea | null>(null);
  const [maxImages, setMaxImages] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [unreadable, setUnreadable] = useState(false);

  useEffect(() => {
    getHealth().then(
      (health) => setMaxImages(health.policy.max_images),
      () => setMaxImages(null),
    );
  }, []);

  useEffect(() => {
    if (!busy) return;
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => {
      clearTimeout(timer);
      setSlow(false);
    };
  }, [busy]);

  // A file that is not a readable picture never reaches the cropper, so report it up front.
  const photo = state?.src;
  useEffect(() => {
    if (!photo) return;
    setUnreadable(false);
    const probe = new Image();
    probe.onerror = () => {
      setUnreadable(true);
      setProblem("bad-photo");
    };
    probe.src = photo;
  }, [photo]);

  if (!state?.src) {
    return (
      <main className="mx-auto grid max-w-[390px] gap-5 px-4 py-10 text-center">
        <h1 className="font-serif text-title font-bold">Chưa có ảnh nào</h1>
        <p className="text-ink-soft">Hãy quay lại và chụp hoặc chọn một ảnh mắt cá.</p>
        <Link
          to="/"
          className="flex min-h-[52px] items-center justify-center rounded-control border-[1.5px] border-navy bg-navy font-semibold text-white"
        >
          Về màn kiểm tra
        </Link>
      </main>
    );
  }

  const { src, source } = state;

  function handleRetake(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    URL.revokeObjectURL(src);
    setCrop({ x: 0, y: 0 });
    setZoom(MIN_ZOOM);
    setProblem(null);
    navigate("/khoanh-mat-ca", {
      replace: true,
      state: { ...state, src: URL.createObjectURL(file) },
    });
  }

  async function handleAnalyse() {
    if (!area) return;
    setBusy(true);
    setProblem(null);
    try {
      const jpeg = await cropToJpeg(src, area);
      inspectionId.current ??= (await createInspection()).id;
      await uploadImage(inspectionId.current, jpeg);
      navigate(`/ket-qua/${inspectionId.current}`, { replace: true });
    } catch (caught) {
      setProblem(classify(caught));
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex h-dvh max-w-[390px] flex-col">
      <header className="grid grid-cols-[44px_1fr_auto] items-center gap-2 px-4 py-3">
        <button
          type="button"
          aria-label="Đóng"
          disabled={busy}
          onClick={() => navigate(-1)}
          className="grid size-11 place-items-center rounded-full border-[1.5px] border-navy disabled:opacity-40"
        >
          <CloseIcon />
        </button>
        <h1 className="text-center font-serif text-title font-bold">Khoanh mắt cá</h1>
        <span className="flex min-w-11 justify-end">
          {maxImages !== null && (
            <Tag>
              Ảnh {(state.imageCount ?? 0) + 1}/{maxImages}
            </Tag>
          )}
        </span>
      </header>

      <div className="relative min-h-0 flex-1 bg-navy">
        {unreadable ? (
          <p className="absolute inset-0 grid place-content-center px-8 text-center text-row-title font-semibold text-white">
            Không mở được ảnh này
          </p>
        ) : (
          <Cropper
            image={src}
            crop={crop}
            zoom={zoom}
            aspect={1}
            minZoom={MIN_ZOOM}
            maxZoom={MAX_ZOOM}
            showGrid
            onCropChange={setCrop}
            onZoomChange={setZoom}
            onCropComplete={(_, pixels) => setArea(pixels)}
            classes={{ cropAreaClassName: "fe-crop-area" }}
          />
        )}
        {busy && (
          <div
            role="status"
            className="absolute inset-0 grid place-content-center justify-items-center gap-3 bg-navy/85 px-6 text-center text-white"
          >
            <span className="size-10 animate-spin rounded-full border-[3px] border-white/30 border-t-coral" />
            <p className="text-row-title font-semibold">Đang phân tích ảnh…</p>
            <p className="text-white/80">
              {slow ? "Lâu hơn thường lệ, bạn chờ thêm chút nhé." : "Thường mất vài giây."}
            </p>
          </div>
        )}
      </div>

      <section className="grid gap-3 px-4 pb-[calc(12px+env(safe-area-inset-bottom))] pt-3">
        {problem ? (
          <Alert>{PROBLEM_TEXT[problem]}</Alert>
        ) : (
          <p className="text-center text-ink-soft">
            Kéo ảnh để mắt cá nằm gọn trong khung vuông. Dùng hai ngón tay để phóng to.
          </p>
        )}

        <div className="grid grid-cols-[44px_1fr_44px] items-center gap-2 rounded-control border-[1.5px] border-navy bg-paper/60 px-1">
          <button
            type="button"
            aria-label="Thu nhỏ"
            disabled={busy || unreadable || zoom <= MIN_ZOOM}
            onClick={() => setZoom(clampZoom(zoom - ZOOM_STEP))}
            className="grid size-11 place-items-center disabled:opacity-40"
          >
            <MinusIcon />
          </button>
          <input
            type="range"
            aria-label="Mức phóng to"
            min={MIN_ZOOM}
            max={MAX_ZOOM}
            step={0.05}
            value={zoom}
            disabled={busy || unreadable}
            onChange={(event) => setZoom(Number(event.target.value))}
            className="h-11 w-full accent-coral-ink"
          />
          <button
            type="button"
            aria-label="Phóng to"
            disabled={busy || unreadable || zoom >= MAX_ZOOM}
            onClick={() => setZoom(clampZoom(zoom + ZOOM_STEP))}
            className="grid size-11 place-items-center disabled:opacity-40"
          >
            <PlusIcon />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Button
            variant="secondary"
            icon={source === "camera" ? <CameraIcon /> : <ImageIcon />}
            disabled={busy}
            onClick={() => retakeInput.current?.click()}
          >
            {source === "camera" ? "Chụp lại" : "Ảnh khác"}
          </Button>
          {problem === "closed" ? (
            <Link
              to="/"
              className="flex min-h-[52px] items-center justify-center rounded-control border-[1.5px] border-navy bg-navy px-4 font-semibold text-white active:opacity-80"
            >
              Lượt mới
            </Link>
          ) : (
            <Button
              variant="accent"
              disabled={busy || !area || problem === "bad-photo"}
              onClick={handleAnalyse}
            >
              Phân tích
              <ArrowRightIcon />
            </Button>
          )}
        </div>
        <input
          ref={retakeInput}
          type="file"
          accept="image/*"
          capture={source === "camera" ? "environment" : undefined}
          hidden
          onChange={handleRetake}
        />
        <Notice className="text-caption" />
      </section>
    </main>
  );
}
