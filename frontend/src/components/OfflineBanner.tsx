import { SignalSlashIcon } from "./icons";
import { useOnlineStatus } from "../hooks/useOnlineStatus";

export default function OfflineBanner() {
  const isOnline = useOnlineStatus();
  if (isOnline) return null;

  return (
    <div className="flex items-center gap-2 bg-pending/10 text-pending border-b border-pending/30 px-4 py-2 text-sm">
      <SignalSlashIcon className="w-4 h-4 shrink-0" />
      <span>Sin red. Tu estado se enviará tan pronto vuelva la señal.</span>
    </div>
  );
}
