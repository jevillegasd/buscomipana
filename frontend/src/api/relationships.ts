import type { RelationshipType } from "./types";

// Display-only Spanish labels for the backend's RelationshipType wire values.
// The values sent to/from the API stay the English literals -- only this
// mapping is localized.
export const RELATIONSHIP_LABELS_ES: Record<RelationshipType, string> = {
  parent: "Padre/Madre",
  child: "Hijo/a",
  sibling: "Hermano/a",
  spouse: "Cónyuge",
  grandparent: "Abuelo/a",
  grandchild: "Nieto/a",
  aunt_or_uncle: "Tío/a",
  niece_or_nephew: "Sobrino/a",
  cousin: "Primo/a",
  guardian: "Tutor/a",
  friend: "Amigo/a",
  other: "Otro",
};

export const RELATIONSHIP_OPTIONS: RelationshipType[] = [
  "parent",
  "child",
  "sibling",
  "spouse",
  "grandparent",
  "grandchild",
  "aunt_or_uncle",
  "niece_or_nephew",
  "cousin",
  "guardian",
  "friend",
  "other",
];
