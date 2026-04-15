import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  CheckSquare,
  RefreshCw,
  Database,
  Search,
  Wrench,
  History,
  CalendarClock,
  FileCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/appStore";

interface NavItem {
  label: string;
  to: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { label: "Dashboard", to: "/", icon: <LayoutDashboard size={18} /> },
  { label: "Accuracy Testing", to: "/accuracy", icon: <CheckSquare size={18} /> },
  { label: "Replay", to: "/replay", icon: <RefreshCw size={18} /> },
  { label: "FIRDS", to: "/firds", icon: <Database size={18} /> },
  { label: "GLEIF", to: "/gleif", icon: <Search size={18} /> },
  { label: "Utilities", to: "/utilities", icon: <Wrench size={18} /> },
  { label: "Scheduler", to: "/scheduler", icon: <CalendarClock size={18} /> },
  { label: "Reconciliation", to: "/reconciliation", icon: <FileCheck size={18} /> },
  { label: "Job History", to: "/jobs", icon: <History size={18} /> },
];

const Sidebar: React.FC = () => {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);

  if (!sidebarOpen) return null;

  return (
    <aside className="w-64 flex-shrink-0 bg-card border-r border-border flex flex-col h-full">
      <div className="px-6 py-5 border-b border-border">
        <span
          className="text-xl font-bold tracking-tight"
          style={{ color: "#D50032" }}
        >
          TXR Automation
        </span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
};

export default Sidebar;
