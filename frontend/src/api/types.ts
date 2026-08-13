export type BloodType = "A+" | "A-" | "B+" | "B-" | "AB+" | "AB-" | "O+" | "O-";
export type PingStatus = "ok" | "distress" | "unknown";
export type RelativeLinkStatus = "pending" | "accepted" | "declined" | "revoked";
export type DistinguishableGender = "male" | "female" | "other" | "prefer_not_to_say";

// Wire values match the backend's RelationshipType enum (app/models/enums.py)
// exactly -- keep in sync. Spanish display labels live in relationships.ts.
export type RelationshipType =
  | "parent"
  | "child"
  | "sibling"
  | "spouse"
  | "grandparent"
  | "grandchild"
  | "aunt_or_uncle"
  | "niece_or_nephew"
  | "cousin"
  | "guardian"
  | "friend"
  | "other";

export interface UserMe {
  id: string;
  phone_number: string;
  full_name: string | null;
  blood_type: BloodType | null;
  birth_date: string | null;
  national_id_number: string | null;
  residence_place: string | null;
  nationality: string | null;
  distinguishable_gender: DistinguishableGender | null;
  role: "user" | "responder" | "admin";
  status: string;
  created_at: string;
  has_profile_photo: boolean;
  needs_privacy_policy_acceptance: boolean;
}

export interface UserPublic {
  id: string;
  full_name: string | null;
  blood_type: BloodType | null;
  birth_date: string | null;
  residence_place: string | null;
  nationality: string | null;
  distinguishable_gender: DistinguishableGender | null;
  national_id_number: string | null;
  has_profile_photo: boolean;
}

export interface PolicyDocument {
  country: string;
  version: string;
  title: string;
  content: string;
}

export interface TermsDocument {
  version: string;
  title: string;
  content: string;
}

export interface OtpRequestResponse {
  detail: string;
  skipped_otp: boolean;
  resend_cooldown_seconds?: number;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  is_new_account: boolean;
}

export interface RelativeLink {
  id: string;
  requester_user_id: string;
  // Null while target_phone_number has no account yet ("unclaimed" --
  // see backend relative_link_service.request_link).
  target_user_id: string | null;
  target_phone_number: string | null;
  relationship_label: RelationshipType | null;
  status: RelativeLinkStatus;
  requested_at: string;
  responded_at: string | null;
}

export interface Ping {
  id: string;
  subject_user_id: string;
  reported_by_user_id: string;
  is_proxy: boolean;
  status: PingStatus;
  message: string | null;
  latitude: number | null;
  longitude: number | null;
  location_accuracy_m: number | null;
  channel: string;
  created_at: string;
}

export interface Pong {
  id: string;
  ping_id: string;
  responder_user_id: string;
  audience: "directed" | "broadcast";
  message: string | null;
  channel: string;
  created_at: string;
}

export interface MissingPersonReport {
  id: string;
  reporter_user_id: string;
  subject_full_name: string;
  subject_phone_number: string;
  relationship: RelationshipType | null;
  notes: string | null;
  last_known_latitude: number | null;
  last_known_longitude: number | null;
  missing_since: string | null;
  missing_location_description: string | null;
  last_known_clothing: string | null;
  body_marks: string | null;
  status: "open" | "matched" | "closed";
  matched_user_id: string | null;
  matched_at: string | null;
  created_at: string;
  has_photo: boolean;
}

export interface MissingPersonMatchCandidate {
  id: string;
  report_id: string;
  candidate_user_id: string;
  phone_similarity_score: number;
  name_similarity_score: number;
  location_score: number | null;
  combined_score: number;
  confirmed: boolean | null;
  created_at: string;
}
