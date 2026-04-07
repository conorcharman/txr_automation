import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import AppLayout from "@/components/layout/AppLayout";
import Dashboard from "@/pages/Dashboard";
import Jobs from "@/pages/Jobs";
import JobDetail from "@/pages/JobDetail";
import ComingSoon from "@/pages/ComingSoon";
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
            <Route path="accuracy" element={<ComingSoon title="Accuracy Testing" />} />
            <Route path="replay" element={<ComingSoon title="Replay" />} />
            <Route path="firds" element={<ComingSoon title="FIRDS" />} />
            <Route path="gleif" element={<ComingSoon title="GLEIF" />} />
            <Route path="utilities" element={<ComingSoon title="Utilities" />} />
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
