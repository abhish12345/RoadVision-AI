import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, ListTodo, GitCompare,
  Menu, X, Activity, ChevronRight
} from 'lucide-react'
import { useState } from 'react'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/tasks',     icon: ListTodo,        label: 'Tasks' },
  { to: '/compare',   icon: GitCompare,      label: 'Compare' },
]

export default function Layout() {
  const [open, setOpen] = useState(true)

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950">

      {/* Sidebar */}
      <aside
        className={`${open ? 'w-56' : 'w-14'} transition-all duration-200 bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0`}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-3 py-4 border-b border-gray-800">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <Activity size={16} className="text-white" />
          </div>
          {open && (
            <div className="flex-1 min-w-0">
              <div className="text-sm font-bold text-white leading-tight truncate">Road ID System</div>
              <div className="text-xs text-gray-500">Survey Analysis</div>
            </div>
          )}
          <button
            onClick={() => setOpen(!open)}
            className="text-gray-600 hover:text-gray-300 transition-colors flex-shrink-0"
          >
            {open ? <X size={15} /> : <ChevronRight size={15} />}
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-3 space-y-0.5 px-2 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-2.5 py-2.5 rounded-lg transition-colors text-sm font-medium
                ${isActive
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/30'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`
              }
            >
              <Icon size={17} className="flex-shrink-0" />
              {open && <span className="truncate">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        {open && (
          <div className="px-3 py-3 border-t border-gray-800">
            <div className="text-xs text-gray-700">v1.0.0 • Road ID System</div>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto min-w-0">
        <Outlet />
      </main>
    </div>
  )
}
