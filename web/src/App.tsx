import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import AppLayout from "@/components/layout/AppLayout";
import Dashboard from "@/pages/Dashboard";
import Jobs from "@/pages/Jobs";
import JobDetail from "@/pages/JobDetail";
import AccuracyTesting from "@/pages/AccuracyTesting";
import Replay from "@/pages/Replay";
import FIRDS from "@/pages/FIRDS";
import GLEIF from "@/pages/GLEIF";
import FCA from "@/pages/FCA";
import Utilities from "@/pages/Utilities";
import Scheduler from "@/pages/Scheduler";
import ReconciliationPage from "@/pages/ReconciliationPage";
import DailyReconciliation from "@/pages/DailyReconciliation";
import DailyReconciliationDetail from "@/pages/DailyReconciliationDetail";
import FileBrowser from "@/pages/FileBrowser";
import DRRCompliance from "@/pages/DRRCompliance";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, staleTime: 30_000 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="accuracy" element={<AccuracyTesting />} />
            <Route path="replay" element={<Replay />} />
            <Route path="firds" element={<FIRDS />} />
            <Route path="gleif" element={<GLEIF />} />
            <Route path="fca" element={<FCA />} />
            <Route path="utilities" element={<Utilities />} />
            <Route path="scheduler" element={<Scheduler />} />
            <Route path="reconciliation" element={<ReconciliationPage />} />
            <Route path="daily-recon" element={<DailyReconciliation />} />
            <Route path="daily-recon/:runId" element={<DailyReconciliationDetail />} />
            <Route path="files" element={<FileBrowser />} />
            <Route path="drr" element={<DRRCompliance />} />
            <Route path="jobs" element={<Jobs />} />
            <Route path="jobs/:jobId" element={<JobDetail />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
