import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { API_BASE_URL, api, ApiError, markLoggedIn } from "../api/client";
import { DEFAULT_COUNTRY } from "../api/countries";
import PhoneNumberInput from "../components/PhoneNumberInput";
import PrivacyPolicyModal from "../components/PrivacyPolicyModal";
import TermsOfServiceModal from "../components/TermsOfServiceModal";
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
  const [showTerms, setShowTerms] = useState(false);
  // Set from the server's response (a masked hint like "b***a@outlook.com"),
  // never something the client supplies -- login-by-email always delivers to
  // whatever's already stored+verified on the account, never a typed-in
  // address (see auth_service.request_login_otp / Issue #10).
  const [emailHint, setEmailHint] = useState<string | null>(null);
  // Switching to email for the first time (last send was still SMS) skips
  // the resend cooldown, same as the backend (see auth_service._create_and_
  // send_otp) -- the email fallback exists specifically for "SMS isn't
  // arriving," so making someone wait out an SMS cooldown before they can
  // even try it would defeat the point. Once email's been used once, normal
  // cooldown applies to it too.
  const emailCooldownApplies = emailHint !== null && resendCooldown > 0;

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => setResendCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  async function sendOtp(useEmail?: boolean) {
    setError(null);
    setLoading(true);
    try {
      const res = await api.post<OtpRequestResponse>("/auth/otp/request", {
        phone_number: phoneNumber,
        use_email: !!useEmail,
      });
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
      setEmailHint(res.email_hint ?? null);
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
    <div className="flex-1 flex flex-col">
      <div className="flex-1 min-h-0 flex flex-col items-center justify-center gap-6 overflow-y-auto px-1 py-4">
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
              {loading ? "Enviando..." : "Login (OTP)"}
            </button>
            <a
              href={`${API_BASE_URL}/manual`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-center text-muted underline decoration-dotted hover:text-ink"
            >
              ¿Primera vez aquí? Ver el manual de usuario
            </a>
            {error && <p className="text-danger text-sm">{error}</p>}
          </form>
        ) : (
          <form onSubmit={verifyCode} className="w-full max-w-xs flex flex-col gap-3">
            <p className="text-sm text-muted">
              {emailHint ? (
                <>
                  Ingresa el código enviado a <span className="text-ink">{emailHint}</span>
                </>
              ) : (
                <>
                  Ingresa el código enviado a <span className="text-ink">{phoneNumber}</span>
                </>
              )}
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
              onClick={() => sendOtp()}
              disabled={loading || resendCooldown > 0}
              className="text-sm text-muted disabled:opacity-50 underline decoration-dotted"
            >
              {resendCooldown > 0 ? `Reenviar código (espera ${resendCooldown}s)` : "Reenviar código"}
            </button>

            <button
              type="button"
              onClick={() => sendOtp(true)}
              disabled={loading || emailCooldownApplies}
              className="text-sm text-muted disabled:opacity-50 underline decoration-dotted"
            >
              {emailCooldownApplies
                ? `Espera ${resendCooldown}s`
                : "¿No te llegó el SMS? Enviar por correo en su lugar"}
            </button>

            <button type="button" onClick={() => setStep("phone")} className="text-sm text-muted underline">
              Usar otro número
            </button>
            {error && <p className="text-danger text-sm">{error}</p>}
          </form>
        )}
      </div>

      <footer className="shrink-0 flex items-center justify-center gap-3 py-4">
        <button
          type="button"
          onClick={() => setShowPolicy(true)}
          className="text-xs text-muted underline decoration-dotted hover:text-ink"
        >
          Política de privacidad
        </button>
        <span className="text-xs text-muted">·</span>
        <button
          type="button"
          onClick={() => setShowTerms(true)}
          className="text-xs text-muted underline decoration-dotted hover:text-ink"
        >
          Términos y condiciones
        </button>
        <span className="text-xs text-muted">·</span>
        <Link to="/about" className="text-xs text-muted underline decoration-dotted hover:text-ink">
          Acerca de
        </Link>
      </footer>

      {showPolicy && <PrivacyPolicyModal mode="readonly" onClose={() => setShowPolicy(false)} />}
      {showTerms && <TermsOfServiceModal onClose={() => setShowTerms(false)} />}
    </div>
  );
}
