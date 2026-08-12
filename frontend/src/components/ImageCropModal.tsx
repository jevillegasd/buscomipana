import { useCallback, useEffect, useState } from "react";
import Cropper, { type Area } from "react-easy-crop";

interface ImageCropModalProps {
  file: File;
  onCancel: () => void;
  onCropped: (blob: Blob) => void;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.addEventListener("load", () => resolve(img));
    img.addEventListener("error", () => reject(new Error("No se pudo cargar la imagen")));
    img.src = src;
  });
}

async function cropToBlob(imageSrc: string, area: Area): Promise<Blob> {
  const image = await loadImage(imageSrc);
  const canvas = document.createElement("canvas");
  canvas.width = area.width;
  canvas.height = area.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("No se pudo procesar la imagen");
  ctx.drawImage(image, area.x, area.y, area.width, area.height, 0, 0, area.width, area.height);
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("No se pudo procesar la imagen"))),
      "image/jpeg",
      0.9,
    );
  });
}

// Square crop picker shared by the profile photo and missing-person report
// photo uploads -- the actual downsize-to-400x400 + re-compression still
// happens server-side (storage/image_processing.process_image) as the source
// of truth, this only lets the user choose *which* square region to keep.
export default function ImageCropModal({ file, onCancel, onCropped }: ImageCropModalProps) {
  const [imageSrc] = useState(() => URL.createObjectURL(file));
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => () => URL.revokeObjectURL(imageSrc), [imageSrc]);

  const handleCropComplete = useCallback((_area: Area, pixels: Area) => setCroppedAreaPixels(pixels), []);

  async function confirm() {
    if (!croppedAreaPixels) return;
    setProcessing(true);
    setError(null);
    try {
      const blob = await cropToBlob(imageSrc, croppedAreaPixels);
      onCropped(blob);
    } catch {
      setError("No se pudo recortar la imagen. Intenta de nuevo.");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-night/95 p-4">
      <div className="w-full max-w-sm rounded-lg bg-card border border-card flex flex-col gap-3 p-3">
        <p className="text-sm font-medium text-ink">Ajusta el recorte</p>
        <div className="relative w-full h-64 bg-night rounded-md overflow-hidden">
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            aspect={1}
            onCropChange={setCrop}
            onZoomChange={setZoom}
            onCropComplete={handleCropComplete}
          />
        </div>
        <input
          type="range"
          min={1}
          max={3}
          step={0.05}
          value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))}
          aria-label="Acercar"
          className="w-full"
        />
        {error && <p className="text-danger text-xs">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="text-sm text-muted hover:text-ink px-3 py-1.5">
            Cancelar
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={processing || !croppedAreaPixels}
            className="rounded-md bg-safe hover:bg-safe/90 disabled:opacity-50 px-4 py-1.5 text-sm font-semibold text-night"
          >
            {processing ? "Procesando..." : "Recortar y continuar"}
          </button>
        </div>
      </div>
    </div>
  );
}
