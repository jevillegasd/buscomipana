import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { PolicyDocument } from "../api/types";

interface PrivacyPolicyModalProps {
  // "readonly" is the public footer link (no session, no accept button).
  // "accept" is the post-login gate -- it blocks the app until "Acepto" is
  // pressed and can't be dismissed any other way.
  mode: "readonly" | "accept";
  onClose?: () => void;
}

export default function PrivacyPolicyModal({ mode, onClose }: PrivacyPolicyModalProps) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["privacy-policy", mode],
    queryFn: () => api.get<PolicyDocument>(mode === "accept" ? "/policy/privacy/me" : "/policy/privacy"),
  });

  const accept = useMutation({
    mutationFn: () => api.post("/policy/privacy/accept"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-night/95 p-4">
      <div className="w-full max-w-lg max-h-[85vh] flex flex-col rounded-lg bg-card border border-card">
        <div className="flex items-center justify-between px-4 py-3 border-b border-night">
          <h2 className="text-lg font-semibold text-ink">{data?.title ?? "Política de privacidad"}</h2>
          {mode === "readonly" && onClose && (
            <button type="button" onClick={onClose} className="text-sm text-muted hover:text-ink">
              Cerrar
            </button>
          )}
        </div>
        <div className="overflow-y-auto px-4 py-3 text-sm text-muted whitespace-pre-wrap">
          {isLoading ? "Cargando..." : data?.content}
        </div>
        {mode === "accept" && (
          <div className="px-4 py-3 border-t border-night flex flex-col gap-2">
            <p className="text-xs text-muted">
              Debes aceptar esta política para continuar usando BuscoMiPana.
            </p>
            <button
              type="button"
              onClick={() => accept.mutate()}
              disabled={isLoading || accept.isPending}
              className="rounded-md bg-safe hover:bg-safe/90 disabled:opacity-50 px-4 py-2 font-semibold text-night self-end"
            >
              {accept.isPending ? "Guardando..." : "Acepto"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
