import type { SexAtBirth } from "./types";

export const SEX_AT_BIRTH_LABELS_ES: Record<SexAtBirth, string> = {
  male: "Masculino",
  female: "Femenino",
  intersex: "Intersexual",
  prefer_not_to_say: "Prefiero no decir",
};

export const SEX_AT_BIRTH_OPTIONS: SexAtBirth[] = ["male", "female", "intersex", "prefer_not_to_say"];
