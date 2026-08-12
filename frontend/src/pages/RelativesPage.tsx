import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../api/client";
import { RELATIONSHIP_LABELS_ES, RELATIONSHIP_OPTIONS } from "../api/relationships";
import { AlertTriangleIcon, CheckCircleIcon, HandshakeIcon } from "../components/icons";
import { useAuthenticatedImage } from "../hooks/useAuthenticatedImage";
import { formatRelativeTime } from "../utils/time";
import type { Ping, RelationshipType, RelativeLink, RelativeLinkStatus, UserMe, UserPublic } from "../api/types";

const LINK_STATUS_LABELS_ES: Record<RelativeLinkStatus, string> = {
  pending: "Pendiente",
  accepted: "Aceptado",
  declined: "Rechazado",
  revoked: "Eliminado",
};

const PING_STATUS_LABELS_ES: Record<string, string> = {
  ok: "ESTÁ BIEN",
  distress: "NECESITA AYUDA",
  unknown: "DESCONOCIDO",
};

function RelativeRow({ link, meId }: { link: RelativeLink; meId: string }) {
  const queryClient = useQueryClient();
  const otherUserId = link.requester_user_id === meId ? link.target_user_id : link.requester_user_id;
  const iAmTarget = link.target_user_id === meId;

  const { data: otherUser } = useQuery({
    queryKey: ["user", otherUserId],
    queryFn: () => api.get<UserPublic>(`/users/${otherUserId}`),
  });
  const photoUrl = useAuthenticatedImage(
    otherUser?.has_profile_photo ? `/users/${otherUserId}/profile-photo` : null,
  );

  const { data: pings } = useQuery({
    queryKey: ["pings-for", otherUserId],
    queryFn: () => api.get<Ping[]>(`/pings?subject_user_id=${otherUserId}`),
    enabled: link.status === "accepted",
  });
  const latest = pings?.[0];

  const respond = useMutation({
    mutationFn: (accept: boolean) =>
      api.post<RelativeLink>(`/relative-links/${link.id}/${accept ? "accept" : "decline"}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["relative-links"] }),
  });

  const revoke = useMutation({
    mutationFn: () => api.del<RelativeLink>(`/relative-links/${link.id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["relative-links"] }),
  });

  const displayName = otherUser?.full_name || "(sin nombre)";

  return (
    <li className="rounded-md border border-card bg-card/50 p-3 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-card overflow-hidden shrink-0 flex items-center justify-center">
            {photoUrl && <img src={photoUrl} alt="" className="w-full h-full object-cover" />}
          </div>
          <span className="font-semibold text-ink flex items-center gap-1">
            {link.status === "accepted" && <HandshakeIcon className="w-4 h-4 text-brand" />}
            {displayName}
          </span>
        </div>
        <span className="text-xs text-muted">
          {link.relationship_label ? RELATIONSHIP_LABELS_ES[link.relationship_label] : LINK_STATUS_LABELS_ES[link.status]}
        </span>
      </div>

      {link.status === "accepted" && latest && (
        <p className="text-xs text-muted flex items-center gap-1">
          {latest.status === "distress" ? (
            <AlertTriangleIcon className="w-3.5 h-3.5 text-danger" />
          ) : (
            <CheckCircleIcon className="w-3.5 h-3.5 text-safe" />
          )}
          Estado: {PING_STATUS_LABELS_ES[latest.status]} · {formatRelativeTime(latest.created_at)}
          {latest.latitude != null && ` · ${latest.latitude.toFixed(3)}, ${latest.longitude!.toFixed(3)}`}
        </p>
      )}

      {link.status === "pending" && iAmTarget && (
        <div className="flex flex-col gap-2 mt-1">
          <p className="text-xs text-muted">
            ¿Quieres vincularte con <span className="text-ink">{displayName}</span> para saber si está bien?
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => respond.mutate(true)}
              className="text-xs rounded bg-safe text-night font-semibold hover:bg-safe/90 px-2 py-1"
            >
              Aceptar
            </button>
            <button
              onClick={() => respond.mutate(false)}
              className="text-xs rounded bg-card text-ink hover:bg-card/70 px-2 py-1"
            >
              Rechazar
            </button>
          </div>
        </div>
      )}
      {link.status === "pending" && !iAmTarget && (
        <p className="text-xs text-muted">Esperando que acepten...</p>
      )}
      {link.status === "accepted" && (
        <button
          onClick={() => revoke.mutate()}
          className="text-xs text-danger hover:text-danger/80 self-start mt-1"
        >
          Eliminar vínculo
        </button>
      )}
    </li>
  );
}

export default function RelativesPage() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: () => api.get<UserMe>("/users/me") });
  const { data: links } = useQuery({
    queryKey: ["relative-links"],
    queryFn: () => api.get<RelativeLink[]>("/relative-links"),
  });

  const [phone, setPhone] = useState("+57");
  const [relationship, setRelationship] = useState<RelationshipType | "">("");
  const [error, setError] = useState<string | null>(null);

  const requestLink = useMutation({
    mutationFn: () =>
      api.post<RelativeLink>("/relative-links", {
        target_phone_number: phone,
        relationship_label: relationship || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["relative-links"] });
      setPhone("+57");
      setRelationship("");
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo enviar la solicitud"),
  });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-ink">Tus panas</h1>
      <p className="text-sm text-muted">
        La ubicación solo se comparte cuando ambas partes aceptan el vínculo. Cualquiera puede eliminarlo en
        cualquier momento.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          requestLink.mutate();
        }}
        className="flex flex-col gap-2 border border-card rounded-md p-3"
      >
        <p className="text-sm font-medium text-ink">Vincular a un pana por número de teléfono</p>
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+573001234567"
          className="rounded-md bg-card border border-card px-3 py-2 text-ink"
        />
        <select
          value={relationship}
          onChange={(e) => setRelationship(e.target.value as RelationshipType)}
          className="rounded-md bg-card border border-card px-3 py-2 text-ink"
        >
          <option value="">Parentesco (opcional)</option>
          {RELATIONSHIP_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {RELATIONSHIP_LABELS_ES[r]}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={requestLink.isPending}
          className="rounded-md bg-brand hover:bg-brand/90 disabled:opacity-50 px-4 py-2 font-semibold text-night"
        >
          Enviar solicitud de vínculo
        </button>
        {error && <p className="text-danger text-sm">{error}</p>}
      </form>

      <ul className="flex flex-col gap-2">
        {me && links?.map((link) => <RelativeRow key={link.id} link={link} meId={me.id} />)}
      </ul>
    </div>
  );
}
