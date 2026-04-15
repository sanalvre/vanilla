import { useEffect, useState, useCallback } from "react";
import { useVaultStore } from "./stores/vaultStore";
import { useStatusStore } from "./stores/statusStore";
import { startVaultWatcher, stopVaultWatcher } from "./api/fileWatcher";
import { checkHealth } from "./api/sidecar";
import { DropZone } from "./components/layout/DropZone";
import { UrlBar } from "./components/layout/UrlBar";
import { IngestStatus } from "./components/layout/IngestStatus";
import { OnboardingFlow } from "./components/onboarding/OnboardingFlow";
import { ProposalPanel } from "./components/proposals/ProposalPanel";

function App() {
  const {
    initialized,
    loading,
    sidecarConnected,
    cleanVaultPath,
    wikiVaultPath,
    vaultWarnings,
    checkInitialization,
    setSidecarConnected,
    setVaultPaths,
  } = useVaultStore();

  const { agentStatus, pendingProposals, startPolling, stopPolling } =
    useStatusStore();

  // Ingestion job tracking
  const [ingestJobs, setIngestJobs] = useState<
    Array<{
      jobId: string;
      label: string;
      status: "pending" | "processing" | "complete" | "error";
      progress: number;
    }>
  >([]);

  const handleIngestStarted = useCallback(
    (jobId: string, source: string) => {
      const label = source.split(/[/\\]/).pop() || source;
      setIngestJobs((prev) => [
        ...prev,
        { jobId, label, status: "pending", progress: 0 },
      ]);
    },
    [],
  );

  const handleIngestError = useCallback((error: string) => {
    console.error("Ingest error:", error);
    // TODO: Show toast notification (Phase 7)
  }, []);

  const handleJobComplete = useCallback(
    (_jobId: string, _outputPath: string) => {
      // File landed in clean-vault — refresh file tree (Phase 7)
    },
    [],
  );

  // Proposal panel visibility
  const [proposalPanelOpen, setProposalPanelOpen] = useState(false);

  // Auto-open panel when new proposals arrive
  useEffect(() => {
    if (pendingProposals > 0) {
      setProposalPanelOpen(true);
    }
  }, [pendingProposals]);

  // Check sidecar health and vault state on mount
  useEffect(() => {
    const init = async () => {
      try {
        const health = await checkHealth();
        setSidecarConnected(health.status === "ok");
      } catch {
        setSidecarConnected(false);
      }
      await checkInitialization();
    };

    init();
  }, [checkInitialization, setSidecarConnected]);

  // Start status polling when initialized and connected
  useEffect(() => {
    if (initialized && sidecarConnected) {
      startPolling();
      return () => stopPolling();
    }
  }, [initialized, sidecarConnected, startPolling, stopPolling]);

  // Start file watcher when vault paths are known
  useEffect(() => {
    if (cleanVaultPath && wikiVaultPath) {
      // Vault root is the parent of clean-vault
      const vaultRoot = cleanVaultPath.replace(/\/clean-vault$/, "");
      startVaultWatcher(cleanVaultPath, wikiVaultPath, vaultRoot).catch(
        (err) => {
          console.warn("File watcher not available (dev mode?):", err);
        },
      );

      return () => {
        stopVaultWatcher();
      };
    }
  }, [cleanVaultPath, wikiVaultPath]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-stone-500">Loading Vanilla...</p>
      </div>
    );
  }

  return (
    <DropZone
      onIngestStarted={handleIngestStarted}
      onError={handleIngestError}
    >
      <div className="flex h-full flex-col">
        {/* Top bar */}
        <header className="flex items-center justify-between border-b border-stone-200 px-4 py-2">
          <h1 className="text-lg font-semibold tracking-tight">Vanilla</h1>
          <div className="flex items-center gap-3 text-sm text-stone-500">
            {initialized && sidecarConnected && (
              <UrlBar
                onIngestStarted={handleIngestStarted}
                onError={handleIngestError}
              />
            )}
            <span>
              Sidecar:{" "}
              <span
                className={
                  sidecarConnected ? "text-green-600" : "text-red-500"
                }
              >
                {sidecarConnected ? "connected" : "disconnected"}
              </span>
            </span>
          </div>
        </header>

        {/* Vault warnings */}
        {vaultWarnings.length > 0 && (
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
            <strong>Vault warnings:</strong>{" "}
            {vaultWarnings.join("; ")}
          </div>
        )}

        {/* Main content */}
        <main className="flex flex-1 overflow-hidden">
          {!initialized ? (
            <OnboardingFlow
              onComplete={(cleanPath, wikiPath) => {
                setVaultPaths(cleanPath, wikiPath);
              }}
            />
          ) : (
            <div className="flex flex-1">
              {/* Left pane — file tree placeholder */}
              <aside className="w-64 border-r border-stone-200 p-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wider text-stone-400">
                  Clean Vault
                </p>
                <p className="text-sm text-stone-400">
                  File tree (Phase 7)
                </p>
                {cleanVaultPath && (
                  <p className="mt-2 truncate text-xs text-stone-300">
                    {cleanVaultPath}
                  </p>
                )}

                {/* Active ingestion jobs */}
                <IngestStatus
                  jobs={ingestJobs}
                  onJobComplete={handleJobComplete}
                />
              </aside>

              {/* Right pane — proposal panel or content viewer */}
              <section className="flex flex-1 overflow-hidden">
                {proposalPanelOpen ? (
                  <ProposalPanel
                    onClose={() => setProposalPanelOpen(false)}
                  />
                ) : (
                  <div className="flex flex-1 items-center justify-center p-4">
                    <p className="text-sm text-stone-400">
                      Content viewer (Phase 7)
                    </p>
                  </div>
                )}
              </section>
            </div>
          )}
        </main>

        {/* Bottom bar */}
        <footer className="flex items-center justify-between border-t border-stone-200 px-4 py-1.5 text-xs text-stone-400">
          <span>
            Agent:{" "}
            <span
              className={
                agentStatus === "running"
                  ? "text-blue-500"
                  : agentStatus === "error"
                    ? "text-red-500"
                    : ""
              }
            >
              {agentStatus}
            </span>
          </span>
          <span>
            {pendingProposals > 0 ? (
              <button
                onClick={() => setProposalPanelOpen((o) => !o)}
                className="font-medium text-amber-600 underline-offset-2 hover:underline"
              >
                {pendingProposals} proposal{pendingProposals !== 1 ? "s" : ""}{" "}
                pending
              </button>
            ) : (
              "Up to date"
            )}
          </span>
        </footer>
      </div>
    </DropZone>
  );
}

export default App;
