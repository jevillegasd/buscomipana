import { NavLink, useNavigate } from "react-router-dom";
import { api, markLoggedOut } from "../api/client";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${isActive ? "bg-card text-ink" : "text-muted hover:text-ink"}`;

export default function NavBar() {
  const navigate = useNavigate();

  async function logout() {
    try {
      await api.post("/auth/logout");
    } finally {
      markLoggedOut();
      navigate("/login", { replace: true });
    }
  }

  return (
    <nav className="flex items-center justify-between px-4 py-3 border-b border-card">
      <div className="flex gap-1">
        <NavLink to="/" className={linkClass} end>
          Estado
        </NavLink>
        <NavLink to="/relatives" className={linkClass}>
          Familiares
        </NavLink>
        <NavLink to="/missing-persons" className={linkClass}>
          Desaparecidos
        </NavLink>
        <NavLink to="/profile" className={linkClass}>
          Perfil
        </NavLink>
      </div>
      <button onClick={logout} className="text-sm text-muted hover:text-ink">
        Cerrar sesión
      </button>
    </nav>
  );
}
