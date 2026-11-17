import type { ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { HistoryIcon, InspectIcon, StatsIcon } from "./icons";
import { Notice } from "./ui";

const TABS: { to: string; label: string; icon: ReactNode }[] = [
  { to: "/", label: "Kiểm tra", icon: <InspectIcon /> },
  { to: "/lich-su", label: "Lịch sử", icon: <HistoryIcon /> },
  { to: "/thong-ke", label: "Thống kê", icon: <StatsIcon /> },
];

/** Routes that get a wide layout on desktop; every other screen stays a phone-width column. */
const WIDE_ROUTES = ["/lich-su", "/thong-ke"];

/** Page frame: scrolling content, the standing notice, and the bottom navigation. */
export function AppShell() {
  const { pathname } = useLocation();
  const wide = WIDE_ROUTES.some((route) => pathname.startsWith(route));
  const column = wide ? "max-w-[390px] lg:max-w-[960px]" : "max-w-[390px]";
  // Result screens carry the floating assistant bubble; the extra room keeps it off the last lines.
  const bottom = pathname.startsWith("/ket-qua") ? "pb-[calc(168px+env(safe-area-inset-bottom))]" : "pb-[calc(88px+env(safe-area-inset-bottom))]";

  return (
    <div className="min-h-dvh">
      <main className={`mx-auto px-4 pt-6 ${bottom} ${column}`}>
        <Outlet />
        <Notice className="mt-8" />
      </main>

      <nav
        aria-label="Điều hướng chính"
        className="fixed inset-x-0 bottom-0 border-t border-rule bg-seaglass/95 backdrop-blur-sm"
      >
        <ul className="mx-auto grid max-w-[390px] grid-cols-3 pb-[env(safe-area-inset-bottom)]">
          {TABS.map((tab) => (
            <li key={tab.to}>
              <NavLink
                to={tab.to}
                end={tab.to === "/"}
                className={({ isActive }) =>
                  `relative grid min-h-16 place-items-center content-center gap-1 text-caption font-semibold ${
                    isActive ? "text-navy" : "text-ink-muted"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span className={isActive ? "text-coral-ink" : undefined}>{tab.icon}</span>
                    {tab.label}
                    {isActive && (
                      <span className="absolute bottom-1.5 h-[3px] w-6 rounded-full bg-coral" />
                    )}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
