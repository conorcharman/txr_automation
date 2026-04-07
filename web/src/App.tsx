import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import AppLayout from "@/components/layout/AppLayout";
import Dashboard from "@/pages/Dashboard";
import Jobs from "@/pages/Jobs";
import JobDetail from "@/pages/JobDetail";
import AccuracyTesting from "@/pages/AccuracyTesting";
import Replay from "@/pages/Replay";
import FIRDS from "@/pages/FIRDS";
import GLEIF from "@/pages/GLEIF";
import Utilities from "@/pages/Utilities";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, staleTime: 30_000 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="accuracy" element={<AccuracyTesting />} />
            <Route path="replay" element={<Replay />} />
            <Route path="firds" element={<FIRDS />} />
            <Route path="gleif" element={<GLEIF />} />
            <Route path="utilities" element={<Utilities />} />
            <Route path="jobs" element={<Jobs />} />
            <Route path="jobs/:jobId" element={<JobDetail />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  );
}
