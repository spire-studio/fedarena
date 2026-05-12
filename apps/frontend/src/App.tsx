import { useState } from "react";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import {
  LayoutDashboard,
  Trophy,
  FlaskConical,
  Swords,
  Activity,
  GitCompareArrows,
  Menu,
  X,
} from "lucide-react";
import Dashboard from "./pages/Dashboard";
import Leaderboard from "./pages/Leaderboard";
import Bench from "./pages/Bench";
import Arena from "./pages/Arena";
import Compare from "./pages/Compare";
import Detail from "./pages/Detail";
import BenchDetail from "./pages/BenchDetail";
import Jobs from "./pages/Jobs";
import ThemeToggle from "./components/ThemeToggle";
import SettingsDialog from "./components/SettingsDialog";
import { AgentProvider } from "./context/AgentContext";
import { BenchProvider } from "./context/BenchContext";

const NAV_ITEMS: { to: string; icon: React.ReactNode; label: string; section: string }[] = [
  { to: "/", icon: <LayoutDashboard className="w-4 h-4" />, label: "Dashboard", section: "Overview" },
  { to: "/arena", icon: <Swords className="w-4 h-4" />, label: "Arena", section: "Submit" },
  { to: "/bench", icon: <FlaskConical className="w-4 h-4" />, label: "Bench", section: "Submit" },
  { to: "/leaderboard", icon: <Trophy className="w-4 h-4" />, label: "Leaderboard", section: "Results" },
  { to: "/compare", icon: <GitCompareArrows className="w-4 h-4" />, label: "Compare", section: "Results" },
  { to: "/jobs", icon: <Activity className="w-4 h-4" />, label: "Jobs", section: "Results" },
];

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <BrowserRouter>
      <AgentProvider>
      <BenchProvider>
      <div className="min-h-screen bg-slate-900 flex">
        {/* Sidebar — desktop */}
        <aside className="hidden md:flex flex-col w-56 border-r border-slate-700 bg-slate-900 fixed inset-y-0 z-40">
          <div className="h-14 flex items-center gap-2 px-5 border-b border-slate-700 shrink-0">
            <Link to="/" className="text-lg font-bold text-slate-50 flex items-center gap-2">
              <Swords className="w-5 h-5 text-blue-400" />
              FedArena
            </Link>
          </div>
          <nav className="flex-1 overflow-y-auto py-4 px-3">
            <SidebarNav />
          </nav>
          <div className="border-t border-slate-700 px-3 py-3 flex items-center gap-2">
            <SettingsDialog />
            <ThemeToggle />
          </div>
        </aside>

        {/* Mobile overlay */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
            <aside className="relative w-56 h-full bg-slate-900 border-r border-slate-700 flex flex-col">
              <div className="h-14 flex items-center justify-between px-5 border-b border-slate-700 shrink-0">
                <Link to="/" className="text-lg font-bold text-slate-50 flex items-center gap-2" onClick={() => setSidebarOpen(false)}>
                  <Swords className="w-5 h-5 text-blue-400" />
                  FedArena
                </Link>
                <button onClick={() => setSidebarOpen(false)} className="text-slate-400 hover:text-slate-200">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <nav className="flex-1 overflow-y-auto py-4 px-3" onClick={() => setSidebarOpen(false)}>
                <SidebarNav />
              </nav>
              <div className="border-t border-slate-700 px-3 py-3 flex items-center gap-2">
                <SettingsDialog />
                <ThemeToggle />
              </div>
            </aside>
          </div>
        )}

        {/* Main area */}
        <div className="flex-1 md:ml-56">
          {/* Mobile top bar */}
          <header className="md:hidden sticky top-0 z-30 h-14 flex items-center gap-3 px-4 border-b border-slate-700 bg-slate-900/80 backdrop-blur">
            <button onClick={() => setSidebarOpen(true)} className="text-slate-400 hover:text-slate-200">
              <Menu className="w-5 h-5" />
            </button>
            <Link to="/" className="text-lg font-bold text-slate-50 flex items-center gap-2">
              <Swords className="w-5 h-5 text-blue-400" />
              FedArena
            </Link>
            <div className="ml-auto flex items-center gap-2">
              <SettingsDialog />
              <ThemeToggle />
            </div>
          </header>

          <main className="max-w-6xl mx-auto px-6 py-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/arena" element={<Arena />} />
              <Route path="/bench" element={<Bench />} />
              <Route path="/bench/:id" element={<BenchDetail />} />
              <Route path="/leaderboard" element={<Leaderboard />} />
              <Route path="/compare" element={<Compare />} />
              <Route path="/jobs" element={<Jobs />} />
              <Route path="/submissions/:id" element={<Detail />} />
            </Routes>
          </main>
        </div>
      </div>
      </BenchProvider>
      </AgentProvider>
    </BrowserRouter>
  );
}

function SidebarNav() {
  return (
    <div className="space-y-1">
      {NAV_ITEMS.map((item, i) => {
        const showSection = i === 0 || item.section !== NAV_ITEMS[i - 1].section;
        return (
          <div key={item.to}>
            {showSection && (
              <p className="text-[11px] uppercase tracking-wider text-slate-500 px-3 pt-3 pb-1">
                {item.section}
              </p>
            )}
            <NavLink
              to={item.to}
              end
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-blue-600/20 text-blue-400"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                }`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          </div>
        );
      })}
    </div>
  );
}

export default App;
