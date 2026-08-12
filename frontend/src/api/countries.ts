// Wire calling codes match the backend's allowlist (app/core/countries.py)
// exactly -- keep in sync. BuscoMiPana only accepts accounts from these
// countries right now (see auth_service.request_login_otp).
export interface SupportedCountry {
  isoCode: string;
  callingCode: string;
  label: string;
}

export const SUPPORTED_COUNTRIES: SupportedCountry[] = [
  { isoCode: "CO", callingCode: "57", label: "Colombia" },
  { isoCode: "AE", callingCode: "971", label: "Emiratos Árabes Unidos" },
];

export const DEFAULT_COUNTRY = SUPPORTED_COUNTRIES[0];
