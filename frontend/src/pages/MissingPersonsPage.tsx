import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../api/client";
import { DEFAULT_COUNTRY } from "../api/countries";
import { RELATIONSHIP_LABELS_ES, RELATIONSHIP_OPTIONS } from "../api/relationships";
import ImageCropModal from "../components/ImageCropModal";
import PhoneNumberInput from "../components/PhoneNumberInput";
import { useAuthenticatedImage } from "../hooks/useAuthenticatedImage";
import type { MissingPersonMatchCandidate, MissingPersonReport, RelationshipType } from "../api/types";

const REPORT_STATUS_LABELS_ES: Record<MissingPersonReport["status"], string> = {
  open: "Abierto",
  matched: "Encontrado",
  closed: "Cerrado",
};

function statusColor(status: MissingPersonReport["status"]) {
  return { open: "text-pending", matched: "text-safe", closed: "text-muted" }[status];
}

function CandidateList({ reportId }: { reportId: string }) {
  const queryClient = useQueryClient();
  const { data: candidates } = useQuery({
    queryKey: ["candidates", reportId],
    queryFn: () => api.get<MissingPersonMatchCandidate[]>(`/missing-person-reports/${reportId}/candidates`),
  });

  const confirm = useMutation({
    mutationFn: (candidateUserId: string) =>
      api.post(`/missing-person-reports/${reportId}/candidates/${candidateUserId}/confirm`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["candidates", reportId] });
      queryClient.invalidateQueries({ queryKey: ["missing-reports"] });
    },
  });

  if (!candidates || candidates.length === 0) return null;

  return (
    <ul className="mt-2 flex flex-col gap-1">
      {candidates.map((c) => (
        <li key={c.id} className="text-xs flex items-center justify-between bg-night rounded px-2 py-1">
          <span className="text-ink">
            Coincidencia {(c.combined_score * 100).toFixed(0)}%{c.confirmed && " · confirmada"}
          </span>
          {!c.confirmed && (
            <button
              onClick={() => confirm.mutate(c.candidate_user_id)}
              className="text-safe hover:text-safe/80"
            >
              Confirmar
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

function ReportPhotoSection({ report }: { report: MissingPersonReport }) {
  const queryClient = useQueryClient();
  const photoUrl = useAuthenticatedImage(report.has_photo ? `/missing-person-reports/${report.id}/photo` : null);

  const [file, setFile] = useState<File | null>(null);
  const [pendingCropFile, setPendingCropFile] = useState<File | null>(null);
  const [consentPublic, setConsentPublic] = useState(false);
  const [consentAi, setConsentAi] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("no file");
      const formData = new FormData();
      formData.append("file", file);
      formData.append("consent_public_use", String(consentPublic));
      formData.append("consent_ai_processing", String(consentAi));
      return api.upload<MissingPersonReport>(`/missing-person-reports/${report.id}/photo`, formData);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData<MissingPersonReport[]>(["missing-reports"], (old) =>
        old?.map((r) => (r.id === updated.id ? updated : r)),
      );
      setFile(null);
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo subir la foto"),
  });

  if (report.has_photo) {
    return (
      <div className="mt-2">
        {photoUrl && (
          <img src={photoUrl} alt={report.subject_full_name} className="w-24 h-24 object-cover rounded-md" />
        )}
      </div>
    );
  }

  return (
    <div className="mt-2 flex flex-col gap-2 bg-night rounded-md p-2">
      <p className="text-xs text-muted">
        Estás reportando el estado de un pana que no tiene teléfono a la mano. Agrega una foto para ayudar a
        identificarlo/a.
      </p>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={(e) => {
          const picked = e.target.files?.[0];
          if (picked) setPendingCropFile(picked);
          e.target.value = "";
        }}
        className="text-xs text-muted"
      />
      {file && <p className="text-xs text-safe">Imagen recortada lista para subir.</p>}
      <label className="flex items-start gap-2 text-xs text-muted">
        <input
          type="checkbox"
          checked={consentPublic}
          onChange={(e) => setConsentPublic(e.target.checked)}
          className="mt-0.5"
        />
        Autorizo que esta foto se muestre públicamente para ayudar a encontrar a esta persona.
      </label>
      <label className="flex items-start gap-2 text-xs text-muted">
        <input
          type="checkbox"
          checked={consentAi}
          onChange={(e) => setConsentAi(e.target.checked)}
          className="mt-0.5"
        />
        Autorizo que esta foto sea procesada por inteligencia artificial para buscar coincidencias
        (función futura).
      </label>
      <button
        type="button"
        onClick={() => upload.mutate()}
        disabled={!file || !consentPublic || !consentAi || upload.isPending}
        className="self-start rounded bg-safe text-night font-semibold hover:bg-safe/90 disabled:opacity-40 disabled:cursor-not-allowed text-xs px-3 py-1.5"
      >
        {upload.isPending ? "Subiendo..." : "Subir foto"}
      </button>
      {error && <p className="text-danger text-xs">{error}</p>}
      {pendingCropFile && (
        <ImageCropModal
          file={pendingCropFile}
          onCancel={() => setPendingCropFile(null)}
          onCropped={(blob) => {
            setPendingCropFile(null);
            setFile(new File([blob], "reporte.jpg", { type: "image/jpeg" }));
          }}
        />
      )}
    </div>
  );
}

export default function MissingPersonsPage() {
  const queryClient = useQueryClient();
  const { data: reports } = useQuery({
    queryKey: ["missing-reports"],
    queryFn: () => api.get<MissingPersonReport[]>("/missing-person-reports"),
  });

  const [name, setName] = useState("");
  const [phone, setPhone] = useState(`+${DEFAULT_COUNTRY.callingCode}`);
  const [relationship, setRelationship] = useState<RelationshipType | "">("");
  const [missingSince, setMissingSince] = useState("");
  const [missingLocation, setMissingLocation] = useState("");
  const [lastKnownClothing, setLastKnownClothing] = useState("");
  const [bodyMarks, setBodyMarks] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createReport = useMutation({
    mutationFn: () =>
      api.post<MissingPersonReport>("/missing-person-reports", {
        subject_full_name: name,
        subject_phone_number: phone,
        relationship: relationship || null,
        missing_since: missingSince || null,
        missing_location_description: missingLocation || null,
        last_known_clothing: lastKnownClothing || null,
        body_marks: bodyMarks || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["missing-reports"] });
      setName("");
      setPhone(`+${DEFAULT_COUNTRY.callingCode}`);
      setRelationship("");
      setMissingSince("");
      setMissingLocation("");
      setLastKnownClothing("");
      setBodyMarks("");
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo enviar el reporte"),
  });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-ink">Reportar un pana desaparecido o en pie</h1>
      <p className="rounded-md border border-pending/30 bg-pending/10 text-pending text-xs px-3 py-2">
        BuscoMiPana no es un registro de personas desaparecidas. La información aquí referenciada es visible
        solo a personas con vínculos confirmados u organismos de socorro certificados.
      </p>
      <p className="text-sm text-muted">
        Cruzamos el número de teléfono con las cuentas registradas, incluyendo coincidencias cercanas por
        dígitos mal escritos o nombres similares.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          createReport.mutate();
        }}
        className="flex flex-col gap-2 border border-card rounded-md p-3"
      >
        <input
          required
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            e.target.setCustomValidity("");
          }}
          onInvalid={(e) => e.currentTarget.setCustomValidity("Ingresa el nombre completo.")}
          placeholder="Nombre completo"
          className="rounded-md bg-card border border-card px-3 py-2 text-ink"
        />
        <PhoneNumberInput value={phone} onChange={setPhone} required />
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

        <label className="text-xs text-muted">
          Fecha en que desapareció (opcional)
          <input
            type="date"
            value={missingSince}
            onChange={(e) => setMissingSince(e.target.value)}
            className="mt-1 w-full rounded-md bg-card border border-card px-3 py-2 text-ink"
          />
        </label>
        <input
          value={missingLocation}
          onChange={(e) => setMissingLocation(e.target.value)}
          placeholder="Lugar donde se vio por última vez (opcional)"
          className="rounded-md bg-card border border-card px-3 py-2 text-ink"
        />
        <input
          value={lastKnownClothing}
          onChange={(e) => setLastKnownClothing(e.target.value)}
          placeholder="Última ropa conocida (opcional)"
          className="rounded-md bg-card border border-card px-3 py-2 text-ink"
        />
        <input
          value={bodyMarks}
          onChange={(e) => setBodyMarks(e.target.value)}
          placeholder="Señas particulares: cicatrices, tatuajes, etc. (opcional)"
          className="rounded-md bg-card border border-card px-3 py-2 text-ink"
        />

        <button
          type="submit"
          disabled={createReport.isPending}
          className="rounded-md bg-brand hover:bg-brand/90 disabled:opacity-50 px-4 py-2 font-semibold text-night"
        >
          Enviar reporte
        </button>
        {error && <p className="text-danger text-sm">{error}</p>}
      </form>

      <h2 className="text-lg font-semibold text-ink mt-2">Tus reportes</h2>
      <ul className="flex flex-col gap-2">
        {reports?.map((r) => (
          <li key={r.id} className="rounded-md border border-card bg-card/50 p-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-ink">{r.subject_full_name}</span>
              <span className={`text-xs font-semibold uppercase ${statusColor(r.status)}`}>
                {REPORT_STATUS_LABELS_ES[r.status]}
              </span>
            </div>
            <p className="text-xs text-muted">{r.subject_phone_number}</p>
            {(r.missing_since || r.missing_location_description) && (
              <p className="text-xs text-muted mt-1">
                {r.missing_since && `Desde ${r.missing_since}`}
                {r.missing_since && r.missing_location_description && " · "}
                {r.missing_location_description}
              </p>
            )}
            {r.last_known_clothing && (
              <p className="text-xs text-muted">Ropa: {r.last_known_clothing}</p>
            )}
            {r.body_marks && <p className="text-xs text-muted">Señas: {r.body_marks}</p>}
            <ReportPhotoSection report={r} />
            {r.status === "open" && <CandidateList reportId={r.id} />}
          </li>
        ))}
        {reports?.length === 0 && <p className="text-sm text-muted">Aún no hay reportes.</p>}
      </ul>
    </div>
  );
}
