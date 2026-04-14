import { useEffect, useState } from "react";
import { useVaultStore } from "./stores/vaultStore";

function App() {
  const { initialized, loading, checkInitialization } = useVaultStore();
  const [sidecarStatus, setSidecarStatus] = useState<string>("checking...");

  useEffect(() => {
    // Check sidecar health on mount
    const checkHealth = async () => {
      try {
        const port = useVaultStore.getState().sidecarPort;
        const res = await fetch(`http://127.0.0.1:${port}/health`);
        const data = await res.json();
        setSidecarStatus(data.status === "ok" ? "connected" : "error");
      } catch {
        setSidecarStatus("disconnected");
      }
    };

    checkHealth();
    checkInitialization();
  }, [checkInitialization]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-stone-500">Loading Vanilla...</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between border-b border-stone-200 px-4 py-2">
        <h1 className="text-lg font-semibold tracking-tight">Vanilla</h1>
        <div className="flex items-center gap-3 text-sm text-stone-500">
          <span>
            Sidecar:{" "}
            <span
              className={
                sidecarStatus === "connected"
                  ? "text-green-600"
                  : "text-red-500"
              }
            >
              {sidecarStatus}
            </span>
          </span>
        </div>
      </header>

      {/* Main content */}
      <main className="flex flex-1 overflow-hidden">
        {!initialized ? (
          <div className="flex flex-1 items-center justify-center">
            <div className="max-w-md text-center">
              <h2 className="mb-2 text-xl font-semibold">Welcome to Vanilla</h2>
              <p className="text-stone-500">
                Onboarding flow will go here. Set up your API key and describe
                your vault to get started.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex flex-1">
            {/* Left pane — file tree placeholder */}
            <aside className="w-64 border-r border-stone-200 p-4">
              <p className="text-sm text-stone-400">File tree (Phase 7)</p>
            </aside>

            {/* Right pane — content viewer placeholder */}
            <section className="flex-1 p-4">
              <p className="text-sm text-stone-400">
                Content viewer (Phase 7)
              </p>
            </section>
          </div>
        )}
      </main>

      {/* Bottom bar */}
      <footer className="flex items-center justify-between border-t border-stone-200 px-4 py-1.5 text-xs text-stone-400">
        <span>Agent: idle</span>
        <span>0 proposals pending</span>
      </footer>
    </div>
  );
}

export default App;
