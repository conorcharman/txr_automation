import { create } from "zustand";

interface AppState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  lastVisitedPage: string;
  setLastVisitedPage: (page: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  lastVisitedPage: "/",
  setLastVisitedPage: (page: string) => set({ lastVisitedPage: page }),
}));
