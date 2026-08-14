import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useState, useEffect, useRef } from "react";
import { api, ApiError } from "../api/client";
import { DISTINGUISHABLE_GENDER_LABELS_ES, DISTINGUISHABLE_GENDER_OPTIONS } from "../api/enums_es";
import ImageCropModal from "../components/ImageCropModal";
import { useAuthenticatedImage } from "../hooks/useAuthenticatedImage";
import type { BloodType, DistinguishableGender, UserMe } from "../api/types";

const BLOOD_TYPES: BloodType[] = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

function ProfilePhoto({ user }: { user: UserMe }) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
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

  function handleCropped(blob: Blob) {
    setPendingFile(null);
    upload.mutate(new File([blob], "profile.jpg", { type: "image/jpeg" }));
  }

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
            if (file) setPendingFile(file);
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
      {pendingFile && (
        <ImageCropModal file={pendingFile} onCancel={() => setPendingFile(null)} onCropped={handleCropped} />
      )}
    </div>
  );
}

function EmailSettings({ user }: { user: UserMe }) {
  const queryClient = useQueryClient();
  const [newEmail, setNewEmail] = useState("");
  const [step, setStep] = useState<"idle" | "code">("idle");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => setResendCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const requestChange = useMutation({
    mutationFn: () =>
      api.post<{ detail: string; resend_cooldown_seconds?: number }>("/auth/email/request", {
        new_email: newEmail,
      }),
    onSuccess: (res) => {
      setError(null);
      setStep("code");
      setResendCooldown(res.resend_cooldown_seconds ?? 60);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo enviar el código"),
  });

  const confirmChange = useMutation({
    mutationFn: () => api.post("/auth/email/confirm", { new_email: newEmail, code }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      setStep("idle");
      setCode("");
      setNewEmail("");
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Código inválido"),
  });

  // Mirrors auth_service.request_email_change's PhoneNotVerified guard --
  // an account can't associate an email until it's proven it actually
  // controls its own phone number (a real SMS-delivered OTP consumed).
  // Logging in via SMS once sets this automatically; nothing extra to do
  // here beyond explaining why the option isn't available yet.
  if (!user.phone_verified) {
    return (
      <div className="rounded-md bg-card border border-card p-3 text-sm text-muted">
        Verifica tu número por SMS (cerrando sesión y volviendo a entrar) para poder asociar un correo de
        respaldo.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-md bg-card border border-card p-3">
      <h2 className="text-sm font-semibold text-ink">Correo de respaldo</h2>
      <p className="text-xs text-muted">
        Úsalo para recibir tu código de acceso si alguna vez no te llega el SMS.
      </p>
      {user.email && user.email_verified && <p className="text-sm text-ink">Actual: {user.email}</p>}

      {step === "idle" ? (
        <div className="flex flex-col gap-2">
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder={user.email ? "Nuevo correo" : "tucorreo@ejemplo.com"}
            className="w-full rounded-md bg-night border border-card px-3 py-2 text-ink"
          />
          <button
            type="button"
            onClick={() => requestChange.mutate()}
            disabled={!newEmail || requestChange.isPending}
            className="self-start rounded-md bg-brand hover:bg-brand/90 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-night"
          >
            {requestChange.isPending ? "Enviando..." : user.email ? "Cambiar correo" : "Agregar correo"}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted">
            Ingresa el código enviado a <span className="text-ink">{newEmail}</span>
          </p>
          <input
            type="text"
            inputMode="numeric"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="123456"
            className="w-full rounded-md bg-night border border-card px-3 py-2 text-ink tracking-widest text-center"
          />
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => confirmChange.mutate()}
              disabled={!code || confirmChange.isPending}
              className="rounded-md bg-safe hover:bg-safe/90 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-night"
            >
              {confirmChange.isPending ? "Verificando..." : "Verificar"}
            </button>
            <button
              type="button"
              onClick={() => requestChange.mutate()}
              disabled={resendCooldown > 0 || requestChange.isPending}
              className="text-sm text-muted disabled:opacity-50 underline decoration-dotted"
            >
              {resendCooldown > 0 ? `Reenviar (${resendCooldown}s)` : "Reenviar código"}
            </button>
            <button
              type="button"
              onClick={() => {
                setStep("idle");
                setCode("");
                setError(null);
              }}
              className="text-sm text-muted underline"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
      {error && <p className="text-danger text-xs">{error}</p>}
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
  const [residencePlace, setResidencePlace] = useState("");
  const [nationality, setNationality] = useState("");
  const [distinguishableGender, setDistinguishableGender] = useState<DistinguishableGender | "">("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name ?? "");
      setBloodType(user.blood_type ?? "");
      setBirthDate(user.birth_date ?? "");
      setNationalIdNumber(user.national_id_number ?? "");
      setResidencePlace(user.residence_place ?? "");
      setNationality(user.nationality ?? "");
      setDistinguishableGender(user.distinguishable_gender ?? "");
    }
  }, [user]);

  const mutation = useMutation({
    mutationFn: () =>
      api.patch<UserMe>("/users/me", {
        full_name: fullName || null,
        blood_type: bloodType || null,
        birth_date: birthDate || null,
        national_id_number: nationalIdNumber || null,
        residence_place: residencePlace || null,
        nationality: nationality || null,
        distinguishable_gender: distinguishableGender || null,
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
      {user && <EmailSettings user={user} />}

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
          Género distinguible
          <select
            value={distinguishableGender}
            onChange={(e) => setDistinguishableGender(e.target.value as DistinguishableGender)}
            className="mt-1 w-full rounded-md bg-card border border-card px-3 py-2 text-ink"
          >
            <option value="">Prefiero no especificar</option>
            {DISTINGUISHABLE_GENDER_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {DISTINGUISHABLE_GENDER_LABELS_ES[s]}
              </option>
            ))}
          </select>
          <span className="block mt-1 text-xs text-muted">
            Cómo te ves para que un rescatista pueda reconocerte, no un dato legal.
          </span>
        </label>

        <label className="text-sm text-muted">
          Lugar de residencia
          <input
            value={residencePlace}
            onChange={(e) => setResidencePlace(e.target.value)}
            placeholder="Ciudad, país donde vives actualmente"
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
