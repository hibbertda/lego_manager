import { useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Blocks, LogOut, Menu, Moon, Package, Plus, Settings, Star, Sun, Wrench } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import TopbarSearch from './TopbarSearch';
import AddSetModal from './AddSetModal';

export default function AppShell({ children }: { children: ReactNode }) {
  const { session, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [addSetOpen, setAddSetOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Auto-close the mobile sidebar drawer whenever the route changes, so
  // navigating to a page doesn't leave the overlay stuck open.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  return (
    <div>
      <header className="topbar">
        <div className="topbar-start">
          <button
            className="menu-toggle"
            aria-label="Toggle navigation menu"
            onClick={() => setSidebarOpen((v) => !v)}
          >
            <Menu size={20} />
          </button>
          <Link to="/sets" className="brand">
            <Blocks className="brand-icon" size={22} />
            <span>LEGO Manager</span>
          </Link>
        </div>
        <TopbarSearch />
        <div className="user-menu">
          <button className="user-menu-trigger" onClick={() => setUserMenuOpen((v) => !v)}>
            <span className="avatar-badge">
              {session?.user?.username?.[0]?.toUpperCase() ?? '?'}
            </span>
            <span>
              {session?.user?.username}
              {session?.user?.is_admin && ' (admin)'}
            </span>
          </button>
          {userMenuOpen && (
            <div className="user-menu-dropdown" onMouseLeave={() => setUserMenuOpen(false)}>
              {session?.user?.is_admin && (
                <Link to="/admin/users" onClick={() => setUserMenuOpen(false)}>
                  <Settings size={15} /> Admin
                </Link>
              )}
              <button onClick={toggleTheme}>
                {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
                {theme === 'dark' ? 'Light mode' : 'Dark mode'}
              </button>
              <button onClick={handleLogout}>
                <LogOut size={15} /> Logout
              </button>
            </div>
          )}
        </div>
      </header>

      <div className="app-shell">
        {sidebarOpen && (
          <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
        )}
        <aside className={sidebarOpen ? 'app-sidebar open' : 'app-sidebar'}>
          <Link to="/sets" className="counter-card">
            <Package className="counter-icon" size={20} />
            <span>
              <span className="counter-value">{session?.owned_set_count ?? 0}</span>
              <span className="counter-label" style={{ display: 'block' }}>
                Set{session?.owned_set_count === 1 ? '' : 's'} Tracked
              </span>
            </span>
          </Link>

          <nav className="nav-group">
            <NavLink to="/sets" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
              <Package size={16} /> My Sets
            </NavLink>
            <NavLink
              to="/wishlist"
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              <Star size={16} /> Wishlist
            </NavLink>
            <button className="nav-button" onClick={() => setAddSetOpen(true)}>
              <Plus size={16} /> Add a Set
            </button>
          </nav>

          <div className="sidebar-footer">
            <nav className="nav-group">
              <NavLink
                to="/utility/labels"
                className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
              >
                <Wrench size={16} /> Utility
              </NavLink>
              {session?.user?.is_admin && (
                <NavLink
                  to="/admin/users"
                  className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
                >
                  <Settings size={16} /> Admin Area
                </NavLink>
              )}
            </nav>
          </div>
        </aside>

        <main className="app-main">{children}</main>
      </div>

      {addSetOpen && <AddSetModal onClose={() => setAddSetOpen(false)} />}
    </div>
  );
}
