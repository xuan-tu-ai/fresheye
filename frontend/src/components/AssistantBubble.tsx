import { Link } from "react-router-dom";

/** The approved assistant mark from the Stitch project: a robot with headphones in a speech bubble. */
export function AssistantIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="7 9 86 84"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <path
        d="M50 14C27 14 12 28 12 47c0 11 6 20 15 26l-4 15 18-8c3 1 6 1 9 1 23 0 38-14 38-34S73 14 50 14Z"
        fill="#fff"
        stroke="currentColor"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="23" y="40" width="5" height="15" rx="2.5" fill="currentColor" />
      <rect x="72" y="40" width="5" height="15" rx="2.5" fill="currentColor" />
      <path d="M26 40c0-9 9-15 24-15s24 6 24 15" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <rect x="29" y="34" width="42" height="27" rx="10" fill="#fff" stroke="currentColor" strokeWidth="4" />
      <ellipse cx="40" cy="46" rx="3.5" ry="5.5" fill="currentColor" />
      <ellipse cx="60" cy="46" rx="3.5" ry="5.5" fill="currentColor" />
      <circle cx="41.5" cy="44" r="1.5" fill="#fff" />
      <circle cx="61.5" cy="44" r="1.5" fill="#fff" />
      <path d="M47 51q3 3 6 0" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

/**
 * Floating entry point to the assistant; sits above the bottom navigation, inside the phone column.
 * Shrinks on short screens so it stays clear of the action buttons.
 */
export function AssistantBubble({ inspectionId }: { inspectionId: number }) {
  return (
    <Link
      to={`/tro-ly/${inspectionId}`}
      aria-label="Hỏi trợ lý FreshEye"
      className="fixed bottom-[calc(72px+env(safe-area-inset-bottom))] right-[max(12px,calc(50vw-183px))] size-[72px] text-navy active:opacity-80 [@media(max-height:700px)]:size-14"
    >
      <AssistantIcon className="size-full drop-shadow-[0_4px_8px_rgb(16_42_69/0.3)]" />
    </Link>
  );
}
