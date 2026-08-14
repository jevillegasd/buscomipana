import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { TermsDocument } from "../api/types";

interface TermsOfServiceModalProps {
  onClose: () => void;
}

export default function TermsOfServiceModal({ onClose }: TermsOfServiceModalProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["terms-of-service"],
    queryFn: () => api.get<TermsDocument>("/policy/terms"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-night/95 p-4">
      <div className="w-full max-w-lg max-h-[85vh] flex flex-col rounded-lg bg-card border border-card">
        <div className="flex items-start justify-between gap-3 px-4 py-3 border-b border-night">
          <h2 className="text-lg font-semibold text-ink">{data?.title ?? "Términos y condiciones"}</h2>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-sm text-muted hover:text-ink"
          >
            Cerrar
          </button>
        </div>
        <div className="overflow-y-auto px-4 py-3 text-sm text-muted whitespace-pre-wrap">
          {isLoading ? "Cargando..." : data?.content}
        </div>
      </div>
    </div>
  );
}
