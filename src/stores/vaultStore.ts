/**
 * Vault store — manages vault paths, initialization state, and sidecar connection.
 *
 * This is the root store that determines whether to show onboarding or the main app.
 */

import { create } from "zustand";

interface VaultState {
  cleanVaultPath: string | null;
  wikiVaultPath: string | null;
  initialized: boolean;
  loading: boolean;
  sidecarPort: number;
  checkInitialization: () => Promise<void>;
  setVaultPaths: (clean: string, wiki: string) => void;
  setSidecarPort: (port: number) => void;
}

export const useVaultStore = create<VaultState>((set, get) => ({
  cleanVaultPath: null,
  wikiVaultPath: null,
  initialized: false,
  loading: true,
  sidecarPort: 8000, // Default; overridden by Tauri on sidecar spawn

  checkInitialization: async () => {
    try {
      const port = get().sidecarPort;
      const res = await fetch(`http://127.0.0.1:${port}/vault/structure`);
      const data = await res.json();
      set({
        initialized: data.initialized,
        cleanVaultPath: data.clean_vault_path,
        wikiVaultPath: data.wiki_vault_path,
        loading: false,
      });
    } catch {
      // Sidecar not running yet — keep loading state
      set({ loading: false, initialized: false });
    }
  },

  setVaultPaths: (clean: string, wiki: string) => {
    set({
      cleanVaultPath: clean,
      wikiVaultPath: wiki,
      initialized: true,
    });
  },

  setSidecarPort: (port: number) => {
    set({ sidecarPort: port });
  },
}));
