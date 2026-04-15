/**
 * useTauriSidecar — listens for the Tauri "sidecar-ready" event
 * and wires the dynamic port into the vault store + localStorage.
 *
 * Only activates when running inside a Tauri window (production app).
 * In dev-browser mode the port comes from ?port=<n> in the URL instead.
 */

import { useEffect } from "react";
import { useVaultStore } from "@/stores/vaultStore";

/** True when running inside the Tauri desktop shell. */
function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function useTauriSidecar() {
  const setSidecarPort = useVaultStore((s) => s.setSidecarPort);
  const setSidecarConnected = useVaultStore((s) => s.setSidecarConnected);

  useEffect(() => {
    if (!isTauri()) return; // Browser dev mode — port comes from URL param

    let unlisten: (() => void) | undefined;

    async function registerListener() {
      try {
        // Dynamic import so the module doesn't break in browser-only mode
        const { listen } = await import("@tauri-apps/api/event");

        unlisten = await listen<number>("sidecar-ready", (event) => {
          const port = event.payload;
          console.log(`[Tauri] Sidecar ready on port ${port}`);

          // Persist for the baseUrl() helper in sidecar.ts
          localStorage.setItem("vanilla:sidecarPort", String(port));

          // Update Zustand store (triggers health check in App.tsx)
          setSidecarPort(port);
          setSidecarConnected(true);
        });
      } catch (err) {
        console.warn("[Tauri] Could not register sidecar-ready listener:", err);
      }
    }

    registerListener();
    return () => unlisten?.();
  }, [setSidecarPort, setSidecarConnected]);
}
