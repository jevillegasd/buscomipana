import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { AlertTriangleIcon, CheckCircleIcon, UsersIcon } from "../components/icons";
import { formatRelativeTime } from "../utils/time";
import type { Ping, PingStatus, RelativeLink, UserMe, UserPublic } from "../api/types";

function captureLocation(): Promise<GeolocationPosition | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve(pos),
      () => resolve(null),
      { timeout: 5000 },
    );
  });
}

const STATUS_LABELS_ES: Record<PingStatus, string> = {
  ok: "BIEN",
  distress: "EN PELIGRO",
  unknown: "DESCONOCIDO",
};

function statusBadge(status: PingStatus) {
  const styles: Record<PingStatus, string> = {
    ok: "bg-safe/15 text-safe",
    distress: "bg-danger/15 text-danger",
    unknown: "bg-card text-muted",
  };
  const Icon = status === "distress" ? AlertTriangleIcon : CheckCircleIcon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${styles[status]}`}>
      <Icon className="w-3.5 h-3.5" />
      {STATUS_LABELS_ES[status]}
    </span>
  );
}

function ReporterName({ userId }: { userId: string }) {
  const { data } = useQuery({
    queryKey: ["user", userId],
    queryFn: () => api.get<UserPublic>(`/users/${userId}`),
  });
  return <>{data?.full_name || "un pana"}</>;
}

function PingHistoryItem({ ping }: { ping: Ping }) {
  return (
    <li className="rounded-md border border-card bg-card/50 p-3 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        {statusBadge(ping.status)}
        <span className="text-xs text-muted">{formatRelativeTime(ping.created_at)}</span>
      </div>
      <p className="text-xs text-muted">
        Vía:{" "}
        {ping.is_proxy ? (
          <>
            Proxy · Reportado por <ReporterName userId={ping.reported_by_user_id} />
          </>
        ) : (
          "Reporte directo"
        )}
      </p>
      {ping.latitude != null && ping.longitude != null && (
        <p className="text-xs text-muted">
          {ping.latitude.toFixed(4)}, {ping.longitude.toFixed(4)}
        </p>
      )}
      {ping.message && <p className="text-xs text-ink italic">&ldquo;{ping.message}&rdquo;</p>}
    </li>
  );
}

function RelativePickOption({
  userId,
  onPick,
}: {
  userId: string;
  onPick: (rel: { id: string; name: string }) => void;
}) {
  const { data } = useQuery({
    queryKey: ["user", userId],
    queryFn: () => api.get<UserPublic>(`/users/${userId}`),
  });
  return (
    <button
      type="button"
      onClick={() => onPick({ id: userId, name: data?.full_name || "(sin nombre)" })}
      className="text-left rounded-md border border-card bg-card px-3 py-2 text-ink hover:border-brand"
    >
      {data?.full_name || "(sin nombre)"}
    </button>
  );
}

function RelativePicker({
  onPick,
  onCancel,
}: {
  onPick: (rel: { id: string; name: string }) => void;
  onCancel: () => void;
}) {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: () => api.get<UserMe>("/users/me") });
  const { data: links } = useQuery({
    queryKey: ["relative-links", "accepted"],
    queryFn: () => api.get<RelativeLink[]>("/relative-links?status_filter=accepted"),
  });

  if (!me || !links) return <p className="text-sm text-muted">Cargando panas...</p>;

  if (links.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-sm text-muted">
          Aún no tienes panas vinculados. Vincula a alguien primero en la pestaña Familiares.
        </p>
        <button type="button" onClick={onCancel} className="text-sm text-muted underline self-start">
          Cancelar
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {links.map((link) => {
        const otherId = link.requester_user_id === me.id ? link.target_user_id : link.requester_user_id;
        return <RelativePickOption key={link.id} userId={otherId} onPick={onPick} />;
      })}
      <button type="button" onClick={onCancel} className="text-sm text-muted underline self-start">
        Cancelar
      </button>
    </div>
  );
}

// Soft client-side cap on the free-text note -- generous for a "short
// message" while leaving headroom for the template text (name + status
// label) within the single-SMS budget. The backend (see
// notification_service.render_ping_message) is the real enforcement point:
// it always fits the total to one 160-character GSM-7 SMS segment, trimming
// the note's tail first if a very long name leaves little room.
const MESSAGE_MAX_LENGTH = 140;

export default function PingsPage() {
  const queryClient = useQueryClient();
  const [shareLocation, setShareLocation] = useState(true);
  const [message, setMessage] = useState("");
  const [picking, setPicking] = useState(false);
  const [reportingFor, setReportingFor] = useState<{ id: string; name: string } | null>(null);

  const { data: pings } = useQuery({
    queryKey: ["my-pings"],
    queryFn: () => api.get<Ping[]>("/users/me/pings"),
  });

  const mutation = useMutation({
    mutationFn: async ({ status, subjectUserId }: { status: "ok" | "distress"; subjectUserId?: string }) => {
      let latitude: number | null = null;
      let longitude: number | null = null;
      let location_accuracy_m: number | null = null;
      if (shareLocation) {
        const position = await captureLocation();
        if (position) {
          latitude = position.coords.latitude;
          longitude = position.coords.longitude;
          location_accuracy_m = Math.round(position.coords.accuracy);
        }
      }
      return api.post<Ping>("/pings", {
        status,
        subject_user_id: subjectUserId ?? null,
        message: message.trim() || null,
        latitude,
        longitude,
        location_accuracy_m,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-pings"] });
      setReportingFor(null);
      setPicking(false);
      setMessage("");
    },
  });

  const showMainButtons = !picking && !reportingFor;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-ink">Reportar estado</h1>

      {!picking && (
        <label className="flex flex-col gap-1 text-sm text-muted">
          Mensaje corto (opcional)
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={MESSAGE_MAX_LENGTH}
            placeholder="Ej: Atrapado en el carro, sin señal"
            className="rounded-md bg-card border border-card px-3 py-2 text-ink"
          />
          <span className="text-xs self-end">
            {message.length}/{MESSAGE_MAX_LENGTH} · se recorta si el total supera 160 caracteres SMS
          </span>
        </label>
      )}

      {showMainButtons && (
        <div className="flex flex-col gap-3">
          <button
            onClick={() => mutation.mutate({ status: "ok" })}
            disabled={mutation.isPending}
            className="min-h-[60px] flex items-center justify-center gap-2 rounded-lg bg-safe hover:bg-safe/90 disabled:opacity-50 py-4 font-bold text-lg text-night"
          >
            <CheckCircleIcon /> ESTOY BIEN
          </button>
          <button
            onClick={() => mutation.mutate({ status: "distress" })}
            disabled={mutation.isPending}
            className="min-h-[60px] flex items-center justify-center gap-2 rounded-lg bg-danger hover:bg-danger/90 disabled:opacity-50 py-4 font-bold text-lg text-night"
          >
            <AlertTriangleIcon /> NECESITO AYUDA
          </button>
          <button
            onClick={() => setPicking(true)}
            disabled={mutation.isPending}
            className="min-h-[60px] flex items-center justify-center gap-2 rounded-lg bg-brand hover:bg-brand/90 disabled:opacity-50 py-4 font-bold text-lg text-night"
          >
            <UsersIcon /> REPORTAR POR UN PANA
          </button>
        </div>
      )}

      {picking && (
        <div className="flex flex-col gap-2 rounded-md border border-card p-3">
          <p className="text-sm text-muted">
            Estás reportando el estado de un pana que no tiene teléfono a la mano. Elige a quién:
          </p>
          <RelativePicker
            onPick={(rel) => {
              setReportingFor(rel);
              setPicking(false);
            }}
            onCancel={() => setPicking(false)}
          />
        </div>
      )}

      {reportingFor && (
        <div className="flex flex-col gap-3 rounded-md border border-card p-3">
          <p className="text-sm text-muted">
            Reportando por <span className="text-ink font-medium">{reportingFor.name}</span>
          </p>
          <button
            onClick={() => mutation.mutate({ status: "ok", subjectUserId: reportingFor.id })}
            disabled={mutation.isPending}
            className="min-h-[60px] flex items-center justify-center gap-2 rounded-lg bg-safe hover:bg-safe/90 disabled:opacity-50 py-4 font-bold text-lg text-night"
          >
            <CheckCircleIcon /> ESTÁ BIEN
          </button>
          <button
            onClick={() => mutation.mutate({ status: "distress", subjectUserId: reportingFor.id })}
            disabled={mutation.isPending}
            className="min-h-[60px] flex items-center justify-center gap-2 rounded-lg bg-danger hover:bg-danger/90 disabled:opacity-50 py-4 font-bold text-lg text-night"
          >
            <AlertTriangleIcon /> NECESITA AYUDA
          </button>
          <button type="button" onClick={() => setReportingFor(null)} className="text-sm text-muted underline self-start">
            Cancelar
          </button>
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-muted">
        <input type="checkbox" checked={shareLocation} onChange={(e) => setShareLocation(e.target.checked)} />
        Compartir ubicación con este reporte (solo visible para familiares aceptados y personal de emergencia
        verificado)
      </label>

      <h2 className="text-lg font-semibold text-ink mt-2">Tu historial</h2>
      <ul className="flex flex-col gap-2">
        {pings?.map((ping) => (
          <PingHistoryItem key={ping.id} ping={ping} />
        ))}
        {pings?.length === 0 && <p className="text-sm text-muted">Aún no hay reportes.</p>}
      </ul>
    </div>
  );
}
