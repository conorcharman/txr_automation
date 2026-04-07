import React from "react";
import { useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fetchHealth } from "@/api/health";
import { useAppStore } from "@/stores/appStore";

const routeTitles: Record<string, string> = {
  "/": "Dashboard",
  "/accuracy": "Accuracy Testing",
  "/replay": "Replay",
  "/firds": "FIRDS",
  "/gleif": "GLEIF",
  "/utilities": "Utilities",
  "/jobs": "Job History",
};

const TopBar: React.FC = () => {
  const location = useLocation();
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const title = routeTitles[location.pathname] ?? "TXR Automation";

  const { data: health, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  const isHealthy = !isError && health?.status === "ok";

  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-border bg-card">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          aria-label="Toggle sidebar"
        >
          <Menu size={18} />
        </Button>
        <h1 className="text-base font-semibold">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full ${
            isHealthy ? "bg-green-500" : "bg-red-500"
          }`}
          aria-label={isHealthy ? "API online" : "API offline"}
        />
        {health?.version && (
          <span className="text-xs text-muted-foreground">v{health.version}</span>
        )}
      </div>
    </header>
  );
};

export default TopBar;
