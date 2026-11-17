import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

import type { Level } from "../api/types";
import { AlertIcon, EyeIcon } from "./icons";

function cx(...parts: (string | false | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/** FreshEye mark and wordmark, as on the Stitch start screen. */
export function Logo() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="grid size-9 place-items-center rounded-full bg-navy text-paper">
        <EyeIcon width={20} height={20} />
      </span>
      <span className="font-serif text-title font-bold">FreshEye</span>
    </span>
  );
}

type ButtonVariant = "primary" | "accent" | "secondary";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-navy text-white",
  accent: "bg-coral text-navy",
  secondary: "bg-paper/60 text-navy",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: ReactNode;
}

export function Button({ variant = "primary", icon, className, children, ...props }: ButtonProps) {
  return (
    <button
      type="button"
      className={cx(
        "flex min-h-[52px] w-full items-center justify-center gap-2.5 rounded-control border-[1.5px] border-navy",
        "px-4 text-body font-semibold transition-opacity active:opacity-80 disabled:opacity-50",
        BUTTON_STYLES[variant],
        className,
      )}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

/** Pill used for filters; `active` marks the selected one. */
export function Chip({ active = false, className, ...props }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cx(
        "min-h-10 rounded-full border-[1.5px] border-navy px-4 text-small font-medium",
        active ? "bg-navy text-white" : "bg-paper text-navy",
        className,
      )}
      {...props}
    />
  );
}

/** Static pill for short facts such as "Ảnh 1/3". */
export function Tag({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cx(
        "inline-flex min-h-8 items-center rounded-full border-[1.5px] border-navy bg-paper px-3 text-small font-medium",
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx("rounded-card border-[1.5px] border-navy bg-paper p-5", className)}
      {...props}
    />
  );
}

/** Small uppercase label that names a card's content. */
export function Label({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cx(
        "text-label font-semibold uppercase tracking-[0.08em] text-ink-soft",
        className,
      )}
      {...props}
    />
  );
}

export const LEVEL_NAMES: Record<Level, string> = {
  0: "Rất tươi",
  1: "Tươi",
  2: "Không tươi",
};

const LEVEL_TEXT: Record<Level, string> = {
  0: "text-level-very-fresh",
  1: "text-level-fresh",
  2: "text-level-not-fresh",
};

/**
 * Shape marker for a freshness level: filled circle, half circle, hollow ring.
 * `null` is "no conclusion" and renders a grey dash, never a level colour.
 */
export function LevelMark({ level, className }: { level: Level | null; className?: string }) {
  if (level === null) {
    return (
      <span
        aria-hidden="true"
        className={cx("inline-block h-[3px] w-3 flex-none rounded-sm bg-level-none", className)}
      />
    );
  }
  const fill =
    level === 0
      ? "currentColor"
      : level === 1
        ? "linear-gradient(90deg, currentColor 50%, transparent 50%)"
        : "transparent";
  return (
    <span
      aria-hidden="true"
      style={{ background: fill }}
      className={cx(
        "inline-block size-3 flex-none rounded-full border-2 border-current",
        LEVEL_TEXT[level],
        className,
      )}
    />
  );
}

/** The standing notice shown on every screen. */
export function Notice({ className }: { className?: string }) {
  return (
    <p className={cx("text-center text-small italic text-ink-soft", className)}>
      Công cụ hỗ trợ, không thay thế kiểm định an toàn thực phẩm.
    </p>
  );
}

/** Inline problem report: what went wrong and what to do, in one or two short sentences. */
export function Alert({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p
      role="alert"
      className={cx(
        "grid grid-cols-[auto_1fr] items-start gap-2.5 rounded-control border-[1.5px] border-coral-ink bg-coral-soft px-3 py-2.5 font-medium text-coral-ink",
        className,
      )}
    >
      <AlertIcon className="mt-px flex-none" />
      <span>{children}</span>
    </p>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "inline-block size-10 animate-spin rounded-full border-[3px] border-navy/20 border-t-coral",
        className,
      )}
    />
  );
}

interface StatePanelProps {
  icon: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}

/** Whole-screen state (loading, offline, not found): one icon, one title, one sentence, one action. */
export function StatePanel({ icon, title, children, action }: StatePanelProps) {
  return (
    <section className="grid justify-items-center gap-3 px-2 py-10 text-center">
      <span className="grid size-16 place-items-center rounded-full border-[1.5px] border-navy bg-paper">
        {icon}
      </span>
      <h2 className="font-serif text-title font-bold">{title}</h2>
      <p className="text-ink-soft">{children}</p>
      {action && <div className="mt-2 w-full">{action}</div>}
    </section>
  );
}
