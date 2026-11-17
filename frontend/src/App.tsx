import { useEffect } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AssistantPage } from "./pages/AssistantPage";
import { CropPage } from "./pages/CropPage";
import { HistoryPage } from "./pages/HistoryPage";
import { InspectPage } from "./pages/InspectPage";
import { ResultPage } from "./pages/ResultPage";
import { StatsPage } from "./pages/StatsPage";

/** Names the browser tab after the screen's heading, so history entries and screen readers can tell screens apart. */
function PageTitle() {
  const { pathname } = useLocation();
  useEffect(() => {
    const heading = document.querySelector("h1")?.textContent;
    document.title = heading && heading !== "FreshEye" ? `${heading} · FreshEye` : "FreshEye";
  }, [pathname]);
  return null;
}

export function App() {
  return (
    <BrowserRouter>
      <PageTitle />
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<InspectPage />} />
          <Route path="ket-qua/:id" element={<ResultPage />} />
          <Route path="lich-su" element={<HistoryPage />} />
          <Route path="thong-ke" element={<StatsPage />} />
        </Route>
        <Route path="tro-ly/:id" element={<AssistantPage />} />
        <Route path="khoanh-mat-ca" element={<CropPage />} />
      </Routes>
    </BrowserRouter>
  );
}
