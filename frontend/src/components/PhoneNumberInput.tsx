import { DEFAULT_COUNTRY, SUPPORTED_COUNTRIES } from "../api/countries";

interface PhoneNumberInputProps {
  // Full E.164 value, e.g. "+573001234567" -- same shape every call site
  // already stored in state and sent straight to the API.
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  id?: string;
}

// Longest calling code first so a future 3-digit code that shares a prefix
// with a 2-digit one can't be matched by the shorter one instead -- mirrors
// backend/app/core/countries.resolve_country.
const COUNTRIES_BY_CODE_LENGTH = [...SUPPORTED_COUNTRIES].sort(
  (a, b) => b.callingCode.length - a.callingCode.length,
);

function splitPhoneNumber(value: string): { callingCode: string; local: string } {
  const digits = value.replace(/\D/g, "");
  const country = COUNTRIES_BY_CODE_LENGTH.find((c) => digits.startsWith(c.callingCode));
  if (country) return { callingCode: country.callingCode, local: digits.slice(country.callingCode.length) };
  return { callingCode: DEFAULT_COUNTRY.callingCode, local: digits };
}

// Country-code dropdown + digits-only local number, combined into a single
// E.164 string for the parent. Spaces, dashes, parentheses, letters, etc. are
// stripped as the user types instead of being rejected -- the backend's
// E.164 validator (schemas/common.py) has no tolerance for them, and a
// pasted number with any of those was the actual cause of the "número
// inválido" 422s users were hitting.
export default function PhoneNumberInput({ value, onChange, required, id }: PhoneNumberInputProps) {
  const { callingCode, local } = splitPhoneNumber(value);

  function emit(nextCallingCode: string, nextLocalRaw: string) {
    const digits = nextLocalRaw.replace(/\D/g, "");
    onChange(`+${nextCallingCode}${digits}`);
  }

  return (
    <div className="mt-1 flex gap-2">
      <select
        value={callingCode}
        onChange={(e) => emit(e.target.value, local)}
        aria-label="País"
        className="rounded-md bg-card border border-card px-2 py-2 text-ink text-sm shrink-0"
      >
        {SUPPORTED_COUNTRIES.map((c) => (
          <option key={c.isoCode} value={c.callingCode}>
            {c.label} (+{c.callingCode})
          </option>
        ))}
      </select>
      <input
        id={id}
        type="tel"
        inputMode="numeric"
        required={required}
        value={local}
        onChange={(e) => emit(callingCode, e.target.value)}
        placeholder="3001234567"
        className="flex-1 min-w-0 rounded-md bg-card border border-card px-3 py-2 text-ink"
      />
    </div>
  );
}
