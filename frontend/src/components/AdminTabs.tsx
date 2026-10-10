import { NavLink } from 'react-router-dom';

export default function AdminTabs() {
  return (
    <div className="tabs">
      <NavLink to="/admin/users" className={({ isActive }) => (isActive ? 'active' : '')}>
        Users
      </NavLink>
      <NavLink to="/admin/sso" className={({ isActive }) => (isActive ? 'active' : '')}>
        Single Sign-On
      </NavLink>
      <NavLink to="/admin/brickset" className={({ isActive }) => (isActive ? 'active' : '')}>
        Brickset API
      </NavLink>
      <NavLink to="/admin/rebrickable" className={({ isActive }) => (isActive ? 'active' : '')}>
        Rebrickable API
      </NavLink>
    </div>
  );
}
