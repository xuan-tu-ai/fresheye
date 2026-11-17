/** Line drawing of a fish eye on a coral disc; the start screen's hero, taken from the Stitch design. */
export function EyeIllustration() {
  return (
    <div className="relative mx-auto grid size-40 place-items-center" aria-hidden="true">
      <div className="absolute size-36 rounded-full bg-coral opacity-80" />
      <svg viewBox="0 0 100 100" fill="none" className="relative size-28 text-navy">
        <ellipse
          cx="50"
          cy="50"
          rx="44"
          ry="32"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="1 3"
        />
        <path
          d="M12 50 C26 30, 74 30, 88 50 C74 70, 26 70, 12 50 Z"
          stroke="currentColor"
          strokeWidth="2.5"
        />
        <circle cx="50" cy="50" r="23" stroke="currentColor" strokeWidth="1.8" />
        <circle cx="50" cy="50" r="16" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 1.5" />
        <circle cx="50" cy="50" r="9.5" fill="currentColor" />
        <circle cx="46.5" cy="46.5" r="2.5" fill="#fff" />
        <path d="M50 28v4M50 68v4M28 50h4M68 50h4" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </div>
  );
}
