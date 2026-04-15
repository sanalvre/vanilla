import { useEffect, useState, useCallback, lazy, Suspense } from "react";
import { useVaultStore } from "./stores/vaultStore";
import { useStatusStore } from "./stores/statusStore";
import { useEditorStore } from "./stores/editorStore";
import { startVaultWatcher, stopVaultWatcher } from "./api/fileWatcher";
import { checkHealth } from "./api/sidecar";
import { DropZone } from "./components/layout/DropZone";
import { UrlBar } from "./components/layout/UrlBar";
import { IngestStatus } from "./components/layout/IngestStatus";
import { OnboardingFlow } from "./components/onboarding/OnboardingFlow";
import { ProposalPanel } from "./components/proposals/ProposalPanel";
import { FileTree } from "./components/layout/FileTree";
import { EditorPanel } from "./components/editor/EditorPanel";
import { ResizableSplit } from "./components/layout/ResizableSplit";
import { CommandPalette } from "./components/command/CommandPalette";
import { Logo } from "./components/layout/Logo";
import { SearchPanel } from "./components/layout/SearchPanel";
import { SettingsPanel } from "./components/settings/SettingsPanel";
import { useTauriSidecar } from "./hooks/useTauriSidecar";

// Lazy load graph (pulls Three.js ~500KB)
const GraphPanel = lazy(() =>
  import("./components/graph/GraphPanel").then((m) => ({
    default: m.GraphPanel,
  })),
);

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

  const { agentStatus, currentPhase, pendingProposals, startPolling, stopPolling } =
    useStatusStore();

  // Wire Tauri sidecar port discovery (no-op in browser dev mode)
  useTauriSidecar();

  const graphVisible = useEditorStore((s) => s.graphVisible);
  const graphSplitPercent = useEditorStore((s) => s.graphSplitPercent);
  const setSplitPercent = useEditorStore((s) => s.setSplitPercent);
  const toggleGraph = useEditorStore((s) => s.toggleGraph);

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
  }, []);

  const handleJobComplete = useCallback(
    (_jobId: string, _outputPath: string) => {
      // File landed in clean-vault — tree auto-refreshes via polling
    },
    [],
  );

  // Proposal panel visibility
  const [proposalPanelOpen, setProposalPanelOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Listen for command palette opening proposals
  useEffect(() => {
    const handler = () => setProposalPanelOpen(true);
    window.addEventListener("vanilla:open-proposals", handler);
    return () => window.removeEventListener("vanilla:open-proposals", handler);
  }, []);

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

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Cmd/Ctrl+Shift+G — toggle graph
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "g") {
        e.preventDefault();
        toggleGraph();
      }
      // Cmd/Ctrl+Shift+P — toggle proposals
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "p") {
        e.preventDefault();
        setProposalPanelOpen((o) => !o);
      }
      // Cmd/Ctrl+Shift+F — toggle search
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "f") {
        e.preventDefault();
        setSearchOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [toggleGraph]);

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
          <Logo variant="full" size="md" />
          <div className="flex items-center gap-3 text-sm text-stone-500">
            {initialized && sidecarConnected && (
              <UrlBar
                onIngestStarted={handleIngestStarted}
                onError={handleIngestError}
              />
            )}
            <button
              onClick={() => {
                window.dispatchEvent(
                  new KeyboardEvent("keydown", {
                    key: "k",
                    metaKey: true,
                    bubbles: true,
                  }),
                );
              }}
              className="rounded border border-stone-200 px-2 py-0.5 text-xs text-stone-400 hover:bg-stone-50"
              title="Command palette (Ctrl+K)"
            >
              {"\u2318"}K
            </button>
            {/* Settings gear */}
            <button
              onClick={() => setSettingsOpen((o) => !o)}
              className={`rounded p-1 transition-colors ${
                settingsOpen
                  ? "bg-stone-200 text-stone-700"
                  : "text-stone-400 hover:bg-stone-100 hover:text-stone-700"
              }`}
              title="Settings"
              aria-label="Open settings"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.4" />
                <path
                  d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.4 3.4l.7.7M11.9 11.9l.7.7M11.9 3.4l-.7.7M4.1 11.9l-.7.7"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                />
              </svg>
            </button>

            <span
              className={`h-2 w-2 rounded-full ${
                sidecarConnected ? "bg-green-500" : "bg-red-400"
              }`}
              role="status"
              aria-label={sidecarConnected ? "Sidecar connected" : "Sidecar disconnected"}
              title={sidecarConnected ? "Connected" : "Disconnected"}
            />
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
              {/* Left sidebar — search + file tree */}
              <aside className="flex w-56 shrink-0 flex-col border-r border-stone-200">
                {/* Sidebar header: search toggle */}
                <div className="flex items-center gap-1 border-b border-stone-100 px-2 py-1.5">
                  <button
                    onClick={() => setSearchOpen((o) => !o)}
                    title="Search (Ctrl+Shift+F)"
                    className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-xs transition-colors ${
                      searchOpen
                        ? "bg-stone-200 text-stone-700"
                        : "text-stone-400 hover:bg-stone-100 hover:text-stone-600"
                    }`}
                  >
                    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                      <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.5" />
                      <line x1="10" y1="10" x2="14" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                    </svg>
                    Search
                  </button>
                </div>

                {/* Body: search results or file tree */}
                <div className="flex-1 overflow-y-auto">
                  {searchOpen ? (
                    <SearchPanel onClose={() => setSearchOpen(false)} />
                  ) : (
                    <div className="px-2 py-1">
                      <FileTree />
                    </div>
                  )}
                </div>

                {/* Ingestion status at bottom of sidebar */}
                <IngestStatus
                  jobs={ingestJobs}
                  onJobComplete={handleJobComplete}
                />
              </aside>

              {/* Right area — graph + editor or proposals */}
              <section className="flex flex-1 overflow-hidden">
                {proposalPanelOpen ? (
                  <ProposalPanel
                    onClose={() => setProposalPanelOpen(false)}
                  />
                ) : graphVisible ? (
                  <ResizableSplit
                    splitPercent={graphSplitPercent}
                    onSplitChange={setSplitPercent}
                    top={
                      <Suspense
                        fallback={
                          <div className="flex h-full items-center justify-center text-sm text-stone-400">
                            Loading graph...
                          </div>
                        }
                      >
                        <GraphPanel />
                      </Suspense>
                    }
                    bottom={<EditorPanel />}
                  />
                ) : (
                  <EditorPanel />
                )}
              </section>
            </div>
          )}
        </main>

        {/* Bottom bar */}
        <footer className="flex items-center justify-between border-t border-stone-200 px-4 py-1.5 text-xs text-stone-400">
          <div className="flex items-center gap-3">
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
            {currentPhase && (
              <span className="text-blue-400">{currentPhase}</span>
            )}
          </div>
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

        {/* Command palette overlay */}
        <CommandPalette />

        {/* Settings panel */}
        {settingsOpen && (
          <SettingsPanel onClose={() => setSettingsOpen(false)} />
        )}
      </div>
    </DropZone>
  );
}

export default App;
