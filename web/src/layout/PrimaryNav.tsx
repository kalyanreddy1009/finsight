import { NavLink } from "react-router-dom";
import { PRIMARY_NAV } from "./navItems";

// Bottom tab bar below 768px; floating header pill at 768px and wider (CSS only, same DOM).
// NavLink sets aria-current="page" on the active item.
export function PrimaryNav() {
  return (
    <nav aria-label="Primary" className="primary-nav">
      <ul className="primary-nav-list">
        {PRIMARY_NAV.map(({ path, label, Icon, end }) => (
          <li key={path}>
            <NavLink to={path} end={end} className="primary-nav-link">
              <Icon className="primary-nav-icon" />
              <span className="primary-nav-label">{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
