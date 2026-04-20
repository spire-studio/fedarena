import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import { Trophy, FlaskConical, Swords } from "lucide-react";
import Leaderboard from "./pages/Leaderboard";
import Bench from "./pages/Bench";
import Arena from "./pages/Arena";
import Detail from "./pages/Detail";
import ThemeToggle from "./components/ThemeToggle";
import SettingsDialog from "./components/SettingsDialog";

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-900">
        {/* Nav */}
        <nav className="border-b border-slate-700 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-8">
            <Link to="/" className="text-lg font-bold text-slate-50 flex items-center gap-2">
              <Swords className="w-5 h-5 text-blue-400" />
              FedArena
            </Link>
            <div className="flex gap-1">
              <NavItem to="/" icon={<Trophy className="w-4 h-4" />} label="Leaderboard" />
              <NavItem to="/arena" icon={<Swords className="w-4 h-4" />} label="Arena" />
              <NavItem to="/bench" icon={<FlaskConical className="w-4 h-4" />} label="Bench" />
            </div>
            <div className="ml-auto flex items-center gap-2">
              <SettingsDialog />
              <ThemeToggle />
            </div>
          </div>
        </nav>

        {/* Content */}
        <main className="max-w-6xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/" element={<Leaderboard />} />
            <Route path="/bench" element={<Bench />} />
            <Route path="/arena" element={<Arena />} />
            <Route path="/submissions/:id" element={<Detail />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

function NavItem({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
          isActive
            ? "bg-blue-600/20 text-blue-400"
            : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
        }`
      }
    >
      {icon}
      {label}
    </NavLink>
  );
}

export default App;
