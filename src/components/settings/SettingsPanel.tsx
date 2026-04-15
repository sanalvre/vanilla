/**
 * SettingsPanel — LLM provider configuration (Phase 9).
 *
 * Slide-in panel from the right. Shows current provider,
 * lets the user swap model providers and enter an API key.
 * Validates the key against the sidecar before saving.
 */

import { useState, useEffect, useCallback } from "react";
import { getLLMConfig, validateLLM, type LLMConfig } from "@/api/sidecar";

const PROVIDERS = [
  {
    id: "openai",
    label: "OpenAI",
    models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    keyPlaceholder: "sk-...",
    docsUrl: "https://platform.openai.com/api-keys",
  },
  {
    id: "anthropic",
    label: "Anthropic",
    models: ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"],
    keyPlaceholder: "sk-ant-...",
    docsUrl: "https://console.anthropic.com/keys",
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    models: ["openai/gpt-4o", "anthropic/claude-3.5-sonnet", "meta-llama/llama-3.1-70b-instruct"],
    keyPlaceholder: "sk-or-...",
    docsUrl: "https://openrouter.ai/keys",
  },
  {
    id: "ollama",
    label: "Ollama (local)",
    models: ["llama3.2", "mistral", "gemma2", "phi3"],
    keyPlaceholder: "No key needed",
    docsUrl: "https://ollama.com",
  },
];

interface SettingsPanelProps {
  onClose: () => void;
}

type Status = "idle" | "validating" | "success" | "error";

export function SettingsPanel({ onClose }: SettingsPanelProps) {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [loading, setLoading] = useState(true);

  // Form state
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("gpt-4o-mini");
  const [showKey, setShowKey] = useState(false);

  // Validation state
  const [status, setStatus] = useState<Status>("idle");
  const [statusMsg, setStatusMsg] = useState("");

  useEffect(() => {
    getLLMConfig()
      .then((c) => {
        setConfig(c);
        setProvider(c.provider);
        setBaseUrl(c.base_url ?? "");
        // Pre-fill model from config
        const m = c.models?.["analysis"] || "gpt-4o-mini";
        setModel(m);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const selectedProvider = PROVIDERS.find((p) => p.id === provider) ?? PROVIDERS[0];
  const isOllama = provider === "ollama";

  const handleValidate = useCallback(async () => {
    if (!isOllama && !apiKey.trim()) {
      setStatus("error");
      setStatusMsg("Enter your API key first");
      return;
    }

    setStatus("validating");
    setStatusMsg("");

    try {
      const result = await validateLLM({
        provider,
        api_key: apiKey.trim(),
        base_url: baseUrl.trim() || undefined,
        model,
      });

      if (result.valid) {
        setStatus("success");
        setStatusMsg("Connected — settings saved");
        // Refresh displayed config
        getLLMConfig().then(setConfig).catch(() => {});
      } else {
        setStatus("error");
        setStatusMsg(result.error ?? "Validation failed");
      }
    } catch {
      setStatus("error");
      setStatusMsg("Could not reach sidecar");
    }
  }, [provider, apiKey, baseUrl, model, isOllama]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/10"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside className="fixed right-0 top-0 z-50 flex h-full w-80 flex-col border-l border-stone-200 bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-stone-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-stone-800">Settings</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700"
            aria-label="Close settings"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <line x1="2" y1="2" x2="12" y2="12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              <line x1="12" y1="2" x2="2" y2="12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6">
          {/* Current status banner */}
          {!loading && config && (
            <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${
              config.api_key_set
                ? "bg-green-50 text-green-700"
                : "bg-amber-50 text-amber-700"
            }`}>
              <div className={`h-1.5 w-1.5 rounded-full ${
                config.api_key_set ? "bg-green-500" : "bg-amber-500"
              }`} />
              {config.api_key_set
                ? `Connected · ${config.provider} · ${config.api_key_masked}`
                : "No API key set — agent pipeline will not run"
              }
            </div>
          )}

          {/* Provider selection */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500">
              Provider
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              {PROVIDERS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    setProvider(p.id);
                    setStatus("idle");
                    setStatusMsg("");
                    setModel(p.models[0]);
                  }}
                  className={`rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                    provider === p.id
                      ? "border-stone-800 bg-stone-800 text-white"
                      : "border-stone-200 text-stone-600 hover:border-stone-300 hover:bg-stone-50"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* API key */}
          {!isOllama && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold uppercase tracking-wider text-stone-500">
                  API Key
                </label>
                <a
                  href={selectedProvider.docsUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-stone-400 underline-offset-2 hover:text-stone-600 hover:underline"
                >
                  Get key ↗
                </a>
              </div>
              <div className="relative">
                <input
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => { setApiKey(e.target.value); setStatus("idle"); }}
                  placeholder={selectedProvider.keyPlaceholder}
                  className="w-full rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 pr-9
                             text-xs text-stone-800 placeholder:text-stone-400
                             focus:border-stone-400 focus:bg-white focus:outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowKey((s) => !s)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600"
                  aria-label={showKey ? "Hide key" : "Show key"}
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    {showKey ? (
                      <>
                        <path d="M1 8C1 8 4 3 8 3s7 5 7 5-3 5-7 5-7-5-7-5z" stroke="currentColor" strokeWidth="1.2" fill="none" />
                        <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
                        <line x1="2" y1="2" x2="14" y2="14" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                      </>
                    ) : (
                      <>
                        <path d="M1 8C1 8 4 3 8 3s7 5 7 5-3 5-7 5-7-5-7-5z" stroke="currentColor" strokeWidth="1.2" fill="none" />
                        <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
                      </>
                    )}
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* Ollama base URL */}
          {isOllama && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-stone-500">
                Ollama URL
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => { setBaseUrl(e.target.value); setStatus("idle"); }}
                placeholder="http://localhost:11434"
                className="w-full rounded-lg border border-stone-200 bg-stone-50 px-3 py-2
                           text-xs text-stone-800 placeholder:text-stone-400
                           focus:border-stone-400 focus:bg-white focus:outline-none transition-colors"
              />
              <p className="text-[11px] text-stone-400">
                Make sure Ollama is running locally
              </p>
            </div>
          )}

          {/* Model selection */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-stone-500">
              Default Model
            </label>
            <select
              value={model}
              onChange={(e) => { setModel(e.target.value); setStatus("idle"); }}
              className="w-full rounded-lg border border-stone-200 bg-stone-50 px-3 py-2
                         text-xs text-stone-700 focus:border-stone-400 focus:outline-none
                         transition-colors"
            >
              {selectedProvider.models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            <p className="text-[11px] text-stone-400">
              Used for analysis and proposal generation
            </p>
          </div>

          {/* Validate & save button */}
          <div className="space-y-2">
            <button
              onClick={handleValidate}
              disabled={status === "validating"}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-stone-800
                         px-4 py-2.5 text-xs font-medium text-white transition-colors
                         hover:bg-stone-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {status === "validating" ? (
                <>
                  <div className="h-3 w-3 animate-spin rounded-full border border-white/30 border-t-white" />
                  Testing connection...
                </>
              ) : (
                "Test & Save"
              )}
            </button>

            {/* Status message */}
            {statusMsg && (
              <p className={`text-center text-[11px] ${
                status === "success" ? "text-green-600" : "text-red-500"
              }`}>
                {status === "success" ? "✓ " : "✗ "}{statusMsg}
              </p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-stone-100 px-4 py-3 text-[11px] text-stone-400">
          Keys are stored locally in your vault config file only.
        </div>
      </aside>
    </>
  );
}
