import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, PlayCircle, History, ShieldAlert, Target, ShieldCheck } from 'lucide-react';

export default function Sidebar() {
  const links = [
    { to: "/", icon: LayoutDashboard, label: "Dashboard" },
    { to: "/console", icon: PlayCircle, label: "Live Console" },
    { to: "/history", icon: History, label: "Run History" },
    { to: "/vulnerability", icon: ShieldAlert, label: "Vulnerability" },
    { to: "/scores", icon: Target, label: "Injection Scores" },
    { to: "/defense", icon: ShieldCheck, label: "Defense Comparison" }
  ];

  return (
    <aside className="w-64 bg-[#0d1117] border-r border-[#30363d] flex flex-col">
      <div className="p-6 border-b border-[#30363d]">
        <h1 className="text-xl font-bold flex items-center gap-2 text-gray-100">
          <ShieldAlert className="text-red-500" />
          ReconMind
        </h1>
        <p className="text-xs text-gray-400 mt-1">Agentic Security Pipeline</p>
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${
                isActive
                  ? 'bg-[#1f6feb] text-white font-medium'
                  : 'text-gray-300 hover:bg-[#21262d] hover:text-white'
              }`
            }
          >
            <link.icon size={18} />
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
