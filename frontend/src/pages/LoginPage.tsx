import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, markLoggedIn } from "../api/client";
import { DEFAULT_COUNTRY } from "../api/countries";
import PhoneNumberInput from "../components/PhoneNumberInput";
import PrivacyPolicyModal from "../components/PrivacyPolicyModal";
import type { OtpRequestResponse, TokenPair } from "../api/types";

export default function LoginPage() {
  const navigate = useNavigate();
  const [phoneNumber, setPhoneNumber] = useState(`+${DEFAULT_COUNTRY.callingCode}`);
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [showPolicy, setShowPolicy] = useState(false);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => setResendCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  async function sendOtp() {
    setError(null);
    setLoading(true);
    try {
      const res = await api.post<OtpRequestResponse>("/auth/otp/request", { phone_number: phoneNumber });
      if (res.skipped_otp) {
        // This browser already has a "remember me" grant for this exact
        // number (set on a previous logout) -- the backend logged us in
        // directly instead of sending a code, so skip the code screen too.
        markLoggedIn();
        navigate("/", { replace: true });
        return;
      }
      setStep("code");
      setResendCooldown(res.resend_cooldown_seconds ?? 60);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setResendCooldown(err.retryAfterSeconds ?? 60);
      }
      setError(err instanceof ApiError ? err.message : "No se pudo enviar el código");
    } finally {
      setLoading(false);
    }
  }

  async function requestCode(e: React.FormEvent) {
    e.preventDefault();
    await sendOtp();
  }

  async function verifyCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      // The response also carries the tokens in JSON (for non-browser clients),
      // but the browser flow only needs the HttpOnly cookies the server set.
      await api.post<TokenPair>("/auth/otp/verify", { phone_number: phoneNumber, code });
      markLoggedIn();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Código inválido");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] gap-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-ink">BuscoMiPana</h1>
        <p className="text-muted text-sm mt-1">Ingresa tu celular para conectarte con tus panas.</p>
      </div>

      {step === "phone" ? (
        <form onSubmit={requestCode} className="w-full max-w-xs flex flex-col gap-3">
          <label className="text-sm text-muted">
            Número de teléfono
            <PhoneNumberInput value={phoneNumber} onChange={setPhoneNumber} required />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-safe hover:bg-safe/90 disabled:opacity-50 px-4 py-3 font-semibold text-night"
          >
            {loading ? "Enviando..." : "Enviar código"}
          </button>
          {error && <p className="text-danger text-sm">{error}</p>}
        </form>
      ) : (
        <form onSubmit={verifyCode} className="w-full max-w-xs flex flex-col gap-3">
          <p className="text-sm text-muted">
            Ingresa el código enviado a <span className="text-ink">{phoneNumber}</span>
          </p>
          <input
            type="text"
            inputMode="numeric"
            required
            value={code}
            onChange={(e) => {
              setCode(e.target.value);
              e.target.setCustomValidity("");
            }}
            onInvalid={(e) => e.currentTarget.setCustomValidity("Ingresa el código que te enviamos.")}
            placeholder="123456"
            className="rounded-md bg-card border border-card px-3 py-2 text-ink tracking-widest text-center"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-safe hover:bg-safe/90 disabled:opacity-50 px-4 py-3 font-semibold text-night"
          >
            {loading ? "Verificando..." : "Verificar y continuar"}
          </button>
          <button
            type="button"
            onClick={sendOtp}
            disabled={loading || resendCooldown > 0}
            className="text-sm text-muted disabled:opacity-50 underline decoration-dotted"
          >
            {resendCooldown > 0 ? `Reenviar código (espera ${resendCooldown}s)` : "Reenviar código"}
          </button>
          <button type="button" onClick={() => setStep("phone")} className="text-sm text-muted underline">
            Usar otro número
          </button>
          {error && <p className="text-danger text-sm">{error}</p>}
        </form>
      )}

      <footer className="mt-4">
        <button
          type="button"
          onClick={() => setShowPolicy(true)}
          className="text-xs text-muted underline decoration-dotted hover:text-ink"
        >
          Política de privacidad
        </button>
      </footer>

      {showPolicy && <PrivacyPolicyModal mode="readonly" onClose={() => setShowPolicy(false)} />}
    </div>
  );
}
