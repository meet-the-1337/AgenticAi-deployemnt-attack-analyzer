import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, PlayCircle, History, ShieldAlert,
  Target, ShieldCheck, PanelLeftClose, PanelLeftOpen
} from 'lucide-react';

const links = [
  { to: "/",              icon: LayoutDashboard, label: "Dashboard" },
  { to: "/console",       icon: PlayCircle,      label: "Live Console" },
  { to: "/history",       icon: History,          label: "Run History" },
  { to: "/vulnerability", icon: ShieldAlert,      label: "Vulnerability" },
  { to: "/scores",        icon: Target,           label: "Injection Scores" },
  { to: "/defense",       icon: ShieldCheck,      label: "Defense Matrix" },
];

export default function Sidebar({ collapsed, setCollapsed }) {
  const w = collapsed ? 68 : 240;

  return (
    <aside style={{
      width: w, minWidth: w, maxWidth: w,
      background: 'linear-gradient(180deg, #06090e 0%, #0a0e18 100%)',
      borderRight: '1px solid #1e293b',
      display: 'flex', flexDirection: 'column',
      position: 'relative', zIndex: 30,
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      boxShadow: '4px 0 24px rgba(0,0,0,0.3)',
      overflow: 'hidden',
    }}>

      {/* ── Brand Header ── */}
      <div style={{
        padding: collapsed ? '20px 14px' : '24px 20px',
        borderBottom: '1px solid #1e293b',
        position: 'relative', overflow: 'hidden',
        display: 'flex', alignItems: 'center', gap: 12,
        transition: 'padding 0.3s',
      }}>
        {/* Glow */}
        <div style={{
          position: 'absolute', top: -20, right: -20,
          width: 80, height: 80, borderRadius: '50%',
          background: '#3b82f6', filter: 'blur(50px)', opacity: 0.12,
        }}></div>

        {/* Logo */}
        <div style={{
          width: 36, height: 36, minWidth: 36, borderRadius: 10,
          background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 20px rgba(59,130,246,0.4)',
        }}>
          <ShieldCheck size={20} color="#fff" />
        </div>

        {!collapsed && (
          <div style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>
            <div style={{
              fontSize: 18, fontWeight: 900, color: '#f0f6fc',
              letterSpacing: '-0.02em',
            }}>ReconMind</div>
            <div style={{
              fontSize: 9, color: '#60a5fa', fontWeight: 700,
              textTransform: 'uppercase', letterSpacing: '0.2em', marginTop: 2,
            }}>Agentic Security SOC</div>
          </div>
        )}
      </div>

      {/* ── Toggle Button ── */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={{
          position: 'absolute', top: 28, right: collapsed ? '50%' : 12,
          transform: collapsed ? 'translateX(50%)' : 'none',
          width: 28, height: 28, borderRadius: 8,
          background: '#161b22', border: '1px solid #30363d',
          color: '#8b949e', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'all 0.3s', zIndex: 10,
        }}
        onMouseEnter={e => {
          e.currentTarget.style.background = '#1f2937';
          e.currentTarget.style.color = '#60a5fa';
          e.currentTarget.style.borderColor = '#60a5fa';
        }}
        onMouseLeave={e => {
          e.currentTarget.style.background = '#161b22';
          e.currentTarget.style.color = '#8b949e';
          e.currentTarget.style.borderColor = '#30363d';
        }}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <PanelLeftOpen size={14} /> : <PanelLeftClose size={14} />}
      </button>

      {/* ── Section Label ── */}
      {!collapsed && (
        <div style={{
          padding: '16px 20px 8px',
          fontSize: 9, fontWeight: 800, color: '#475569',
          textTransform: 'uppercase', letterSpacing: '0.18em',
        }}>Navigation</div>
      )}

      {/* ── Nav Links ── */}
      <nav style={{
        padding: collapsed ? '12px 10px' : '4px 12px',
        display: 'flex', flexDirection: 'column', gap: 4,
        flex: 1,
      }}>
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/'}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center',
              gap: 12,
              padding: collapsed ? '12px' : '10px 14px',
              borderRadius: 10,
              fontSize: 13, fontWeight: isActive ? 700 : 500,
              color: isActive ? '#60a5fa' : '#8b949e',
              background: isActive ? 'rgba(59,130,246,0.08)' : 'transparent',
              border: isActive ? '1px solid rgba(59,130,246,0.15)' : '1px solid transparent',
              textDecoration: 'none',
              transition: 'all 0.2s ease',
              position: 'relative',
              justifyContent: collapsed ? 'center' : 'flex-start',
              boxShadow: isActive ? 'inset 0 0 16px rgba(59,130,246,0.06)' : 'none',
              overflow: 'hidden',
              whiteSpace: 'nowrap',
            })}
          >
            {({ isActive }) => (
              <>
                <link.icon size={18} style={{
                  color: isActive ? '#60a5fa' : '#6b7280',
                  transition: 'color 0.2s',
                  flexShrink: 0,
                }} />
                {!collapsed && (
                  <span style={{ transition: 'opacity 0.2s' }}>{link.label}</span>
                )}
                {isActive && !collapsed && (
                  <div style={{
                    marginLeft: 'auto', width: 6, height: 6, borderRadius: '50%',
                    background: '#60a5fa',
                    boxShadow: '0 0 10px rgba(59,130,246,0.8)',
                  }}></div>
                )}
                {isActive && collapsed && (
                  <div style={{
                    position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
                    width: 3, height: 20, borderRadius: '0 4px 4px 0',
                    background: '#60a5fa',
                    boxShadow: '0 0 8px rgba(59,130,246,0.6)',
                  }}></div>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* ── Status Footer ── */}
      <div style={{
        margin: collapsed ? '8px' : '12px',
        padding: collapsed ? '12px 8px' : '14px 16px',
        borderRadius: 12,
        background: '#0f172a',
        border: '1px solid #1e293b',
        transition: 'all 0.3s',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          justifyContent: collapsed ? 'center' : 'flex-start',
        }}>
          {/* Pulsing dot */}
          <div style={{ position: 'relative', width: 8, height: 8, flexShrink: 0 }}>
            <span style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              background: '#34d399', opacity: 0.6,
              animation: 'sidebarPing 2s ease-in-out infinite',
            }}></span>
            <span style={{
              position: 'relative', display: 'block', width: 8, height: 8,
              borderRadius: '50%', background: '#34d399',
            }}></span>
          </div>
          {!collapsed && (
            <span style={{ fontSize: 11, fontWeight: 700, color: '#d1d5db' }}>System Online</span>
          )}
        </div>
        {!collapsed && (
          <div style={{
            fontSize: 10, color: '#475569', fontFamily: 'monospace',
            marginTop: 6,
          }}>Sensors active · Model listening</div>
        )}
      </div>

      <style>{`
        @keyframes sidebarPing {
          0%, 100% { transform: scale(1); opacity: 0.6; }
          50% { transform: scale(2); opacity: 0; }
        }
        aside nav a:hover:not(.active) {
          background: rgba(30, 41, 59, 0.5) !important;
          color: #d1d5db !important;
        }
        aside nav a:hover svg {
          color: #60a5fa !important;
        }
      `}</style>
    </aside>
  );
}
