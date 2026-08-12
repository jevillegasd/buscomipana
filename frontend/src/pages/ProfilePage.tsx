import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useState, useEffect, useRef } from "react";
import { api, ApiError } from "../api/client";
import { SEX_AT_BIRTH_LABELS_ES, SEX_AT_BIRTH_OPTIONS } from "../api/enums_es";
import { useAuthenticatedImage } from "../hooks/useAuthenticatedImage";
import type { BloodType, SexAtBirth, UserMe } from "../api/types";

const BLOOD_TYPES: BloodType[] = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

function ProfilePhoto({ user }: { user: UserMe }) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const photoUrl = useAuthenticatedImage(user.has_profile_photo ? `/users/${user.id}/profile-photo` : null);

  const upload = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.upload<UserMe>("/users/me/profile-photo", formData);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["me"], updated);
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo subir la foto"),
  });

  const remove = useMutation({
    mutationFn: () => api.del("/users/me/profile-photo"),
    onSuccess: () => queryClient.setQueryData(["me"], { ...user, has_profile_photo: false }),
  });

  return (
    <div className="flex items-center gap-4">
      <div className="w-20 h-20 rounded-full bg-card overflow-hidden flex items-center justify-center shrink-0">
        {photoUrl ? (
          <img src={photoUrl} alt="Foto de perfil" className="w-full h-full object-cover" />
        ) : (
          <span className="text-muted text-xs">Sin foto</span>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={upload.isPending}
          className="text-sm rounded bg-card hover:bg-card/70 text-ink disabled:opacity-50 px-3 py-1.5"
        >
          {upload.isPending ? "Subiendo..." : "Cambiar foto"}
        </button>
        {user.has_profile_photo && (
          <button
            type="button"
            onClick={() => remove.mutate()}
            className="text-xs text-danger hover:text-danger/80 self-start"
          >
            Eliminar foto
          </button>
        )}
        {error && <p className="text-danger text-xs">{error}</p>}
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const { data: user } = useQuery({ queryKey: ["me"], queryFn: () => api.get<UserMe>("/users/me") });

  const [fullName, setFullName] = useState("");
  const [bloodType, setBloodType] = useState<BloodType | "">("");
  const [birthDate, setBirthDate] = useState("");
  const [nationalIdNumber, setNationalIdNumber] = useState("");
  const [birthPlace, setBirthPlace] = useState("");
  const [nationality, setNationality] = useState("");
  const [sexAtBirth, setSexAtBirth] = useState<SexAtBirth | "">("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name ?? "");
      setBloodType(user.blood_type ?? "");
      setBirthDate(user.birth_date ?? "");
      setNationalIdNumber(user.national_id_number ?? "");
      setBirthPlace(user.birth_place ?? "");
      setNationality(user.nationality ?? "");
      setSexAtBirth(user.sex_at_birth ?? "");
    }
  }, [user]);

  const mutation = useMutation({
    mutationFn: () =>
      api.patch<UserMe>("/users/me", {
        full_name: fullName || null,
        blood_type: bloodType || null,
        birth_date: birthDate || null,
        national_id_number: nationalIdNumber || null,
        birth_place: birthPlace || null,
        nationality: nationality || null,
        sex_at_birth: sexAtBirth || null,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["me"], updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-ink">Tu perfil</h1>
      <p className="text-sm text-muted">
        Estos datos ayudan al personal de emergencia a identificarte. Teléfono: {user?.phone_number}
      </p>

      {user && <ProfilePhoto user={user} />}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
        className="flex flex-col gap-3"
      >
        <label className="text-sm text-muted">
          Nombre completo
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="mt-1 w-full rounded-md bg-card border border-card px-3 py-2 text-ink"
          />
        </label>

        <label className="text-sm text-muted">
          Tipo de sangre
          <select
            value={bloodType}
            onChange={(e) => setBloodType(e.target.value as BloodType)}
            className="mt-1 w-full rounded-md bg-card border border-card px-3 py-2 text-ink"
          >
            <option value="">Desconocido</option>
            {BLOOD_TYPES.map((bt) => (
              <option key={bt} value={bt}>
                {bt}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-muted">
          Fecha de nacimiento
          <input
            type="date"
            value={birthDate}
            onChange={(e) => setBirthDate(e.target.value)}
            className="mt-1 w-full rounded-md bg-card border border-card px-3 py-2 text-ink"
          />
        </label>

        <label className="text-sm text-muted">
          Sexo al nacer
          <select
            value={sexAtBirth}
            onChange={(e) => setSexAtBirth(e.target.value as SexAtBirth)}
            className="mt-1 w-full rounded-md bg-card border border-card px-3 py-2 text-ink"
          >
            <option value="">Prefiero no especificar</option>
            {SEX_AT_BIRTH_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {SEX_AT_BIRTH_LABELS_ES[s]}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-muted">
          Lugar de nacimiento
          <input
            value={birthPlace}
            onChange={(e) => setBirthPlace(e.target.value)}
            placeholder="Ciudad, país"
            className="mt-1 w-full rounded-md bg-card border border-card px-3 py-2 text-ink"
          />
        </label>

        <label className="text-sm text-muted">
          Nacionalidad
          <input
            value={nationality}
            onChange={(e) => setNationality(e.target.value)}
            placeholder="Colombiana"
            className="mt-1 w-full rounded-md bg-card border border-card px-3 py-2 text-ink"
          />
        </label>

        <label className="text-sm text-muted">
          Número de identificación
          <input
            value={nationalIdNumber}
            onChange={(e) => setNationalIdNumber(e.target.value)}
            placeholder="Cédula o documento"
            className="mt-1 w-full rounded-md bg-card border border-card px-3 py-2 text-ink"
          />
          <span className="block mt-1 text-xs text-muted">
            Solo visible para ti y para familiares vinculados o personal de emergencia verificado.
          </span>
        </label>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="rounded-md bg-safe hover:bg-safe/90 disabled:opacity-50 px-4 py-2 font-semibold text-night"
        >
          {mutation.isPending ? "Guardando..." : "Guardar"}
        </button>
        {saved && <p className="text-safe text-sm">Guardado.</p>}
      </form>
    </div>
  );
}
