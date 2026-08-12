import type { DistinguishableGender } from "./types";

export const DISTINGUISHABLE_GENDER_LABELS_ES: Record<DistinguishableGender, string> = {
  male: "Hombre",
  female: "Mujer",
  other: "Otro",
  prefer_not_to_say: "Prefiero no decir",
};

export const DISTINGUISHABLE_GENDER_OPTIONS: DistinguishableGender[] = ["male", "female", "other", "prefer_not_to_say"];
