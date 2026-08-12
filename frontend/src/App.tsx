import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { isLoggedIn } from "./api/client";
import NavBar from "./components/NavBar";
import OfflineBanner from "./components/OfflineBanner";
import LoginPage from "./pages/LoginPage";
import PingsPage from "./pages/PingsPage";
import ProfilePage from "./pages/ProfilePage";
import RelativesPage from "./pages/RelativesPage";
import MissingPersonsPage from "./pages/MissingPersonsPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  // navigate() (e.g. after login/logout) doesn't re-render App on its own --
  // App isn't otherwise subscribed to router state, so isLoggedIn() would
  // stay frozen at whatever it was on first mount. Subscribing to location
  // forces App to re-render on every route change, which is what makes this
  // plain-function check reactive instead of a one-shot read.
  useLocation();

  return (
    <div className="max-w-lg mx-auto min-h-screen flex flex-col">
      <OfflineBanner />
      {isLoggedIn() && <NavBar />}
      <main className="flex-1 p-4">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <PingsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/profile"
            element={
              <RequireAuth>
                <ProfilePage />
              </RequireAuth>
            }
          />
          <Route
            path="/relatives"
            element={
              <RequireAuth>
                <RelativesPage />
              </RequireAuth>
            }
          />
          <Route
            path="/missing-persons"
            element={
              <RequireAuth>
                <MissingPersonsPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
