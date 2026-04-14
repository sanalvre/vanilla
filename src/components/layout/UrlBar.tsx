/**
 * UrlBar — inline URL paste input for web page ingestion.
 *
 * Appears in the top bar. User pastes a URL and presses Enter
 * to ingest the page as markdown.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { ingestUrl } from "@/api/ingest";

interface UrlBarProps {
  onIngestStarted?: (jobId: string, url: string) => void;
  onError?: (error: string) => void;
}

export function UrlBar({ onIngestStarted, onError }: UrlBarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = url.trim();
      if (!trimmed) return;

      // Basic URL validation
      try {
        new URL(trimmed);
      } catch {
        onError?.("Invalid URL");
        return;
      }

      setLoading(true);
      try {
        const result = await ingestUrl(trimmed);
        onIngestStarted?.(result.job_id, trimmed);
        setUrl("");
        setIsOpen(false);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        onError?.(msg);
      } finally {
        setLoading(false);
      }
    },
    [url, onIngestStarted, onError],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        setUrl("");
      }
    },
    [],
  );

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="rounded px-2 py-1 text-sm text-stone-500 hover:bg-stone-100 hover:text-stone-700"
        title="Paste a URL to ingest (requires internet)"
      >
        + URL
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="text"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Paste URL and press Enter..."
        className="w-64 rounded border border-stone-300 px-2 py-1 text-sm focus:border-amber-400 focus:outline-none"
        disabled={loading}
      />
      {loading && (
        <span className="text-xs text-stone-400">Fetching...</span>
      )}
    </form>
  );
}
