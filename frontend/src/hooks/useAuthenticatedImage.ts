import { useEffect, useState } from "react";
import { api } from "../api/client";

// Photo endpoints are access-controlled (see media_asset_service.py), so
// photos can never be plain <img src="..."> URLs -- that would bypass the
// same visibility check every other sensitive field goes through. Fetches via
// the authenticated client instead and hands back a local object URL.
export function useAuthenticatedImage(path: string | null): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setUrl(null);

    if (!path) return;

    api.getBlob(path).then((blob) => {
      if (cancelled || !blob) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  return url;
}
