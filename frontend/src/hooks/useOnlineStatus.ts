import { useEffect, useState } from "react";

// Not a full offline-first queue (see docs/ARCHITECTURE.md known limitations)
// -- just surfaces connectivity state so the UI can be honest about it,
// per the identity guide's "Sin red" copy.
export function useOnlineStatus(): boolean {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return isOnline;
}
