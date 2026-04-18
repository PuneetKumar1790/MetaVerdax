import { useState, useEffect } from 'react';
import { Routes, Route, NavLink, Link } from 'react-router-dom';
import { MessageSquare, History, FileText, Settings, Menu, X } from 'lucide-react';
import { api } from '../lib/api';
import ChatAgent from '../app/ChatAgent';
import ValidationHistory from '../app/ValidationHistory';
import ReportsView from '../app/ReportsView';

const navItems = [
  { to: '/app', label: 'Chat Agent', icon: MessageSquare, end: true },
  { to: '/app/history', label: 'Validation History', icon: History, end: false },
  { to: '/app/reports', label: 'Reports', icon: FileText, end: false },
];

export default function AppDashboard() {
  const [omConnected, setOmConnected] = useState<boolean | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await api.getHealth();
        setOmConnected(health.openmetadata_connected);
      } catch {
        setOmConnected(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-brand-black flex">
      {/* Mobile header */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 h-14 bg-brand-black/90 backdrop-blur-xl border-b border-white/5 flex items-center justify-between px-4">
        <Link to="/" className="flex items-center">
          <img src="/brand_name.png" alt="MetaVerdax" className="h-11 w-auto" />
        </Link>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="text-white/60 hover:text-white"
          aria-label="Toggle menu"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Sidebar overlay for mobile */}
      {sidebarOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/60 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed md:sticky top-0 left-0 z-40 h-screen w-64 bg-[#0a0a0a] border-r border-white/5 flex flex-col transition-transform duration-300 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-white/5">
          <Link to="/" className="inline-flex items-center">
            <img src="/brand_name.png" alt="MetaVerdax" className="h-12 w-auto" />
          </Link>
        </div>

        {/* Nav Items */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-brand-cyan/10 text-brand-cyan'
                      : 'text-white/40 hover:text-white/70 hover:bg-white/[0.03]'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        {/* Connection Status */}
        <div className="px-5 py-4 border-t border-white/5">
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                omConnected === null
                  ? 'bg-white/20'
                  : omConnected
                  ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]'
                  : 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]'
              }`}
            />
            <span className="text-xs text-white/30">
              {omConnected === null
                ? 'Checking...'
                : omConnected
                ? 'OpenMetadata connected'
                : 'OpenMetadata disconnected'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 min-h-screen pt-14 md:pt-0 overflow-auto">
        <Routes>
          <Route index element={<ChatAgent />} />
          <Route path="history" element={<ValidationHistory />} />
          <Route path="reports" element={<ReportsView />} />
          <Route
            path="settings"
            element={
              <div className="flex items-center justify-center h-full text-white/30">
                <Settings className="w-6 h-6 mr-2" /> Settings coming soon.
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
