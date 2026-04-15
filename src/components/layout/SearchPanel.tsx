/**
 * SearchPanel — full-text search integrated into the left sidebar.
 *
 * When the search input has a query, file tree is replaced with ranked
 * results showing title + snippet. Vault filter tabs narrow the scope.
 * Clicking a result opens it in the editor.
 */

import { useState, useCallback, useRef, memo } from "react";
import { search } from "@/api/sidecar";
import { useEditorStore } from "@/stores/editorStore";

type VaultFilter = "all" | "clean" | "wiki";

interface SearchResult {
  path: string;
  vault: string;
  title: string;
  snippet: string;
  score: number;
}

/* ── Snippet renderer — highlights <mark> tags ───────────────────── */
function Snippet({ html }: { html: string }) {
  // Strip any leading/trailing ellipsis for cleaner display
  const clean = html.replace(/^\.\.\./, "").replace(/\.\.\.$/, "").trim();
  return (
    <p
      className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-stone-400"
      // The backend wraps matches in <mark> — safe, sidecar-generated
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
}

/* ── Single result row ──────────────────────────────────────────────── */
const ResultRow = memo(function ResultRow({
  result,
  onSelect,
}: {
  result: SearchResult;
  onSelect: (path: string) => void;
}) {
  const isWiki = result.vault === "wiki" || result.path.startsWith("wiki-vault/");
  return (
    <button
      onClick={() => onSelect(result.path)}
      className="group w-full rounded-lg px-2 py-2 text-left transition-colors hover:bg-stone-100"
    >
      <div className="flex items-center gap-1.5">
        <span className="flex-1 truncate text-xs font-medium text-stone-700 group-hover:text-stone-900">
          {result.title || result.path.split("/").pop()}
        </span>
        <span
          className={`shrink-0 rounded px-1 py-px text-[9px] font-semibold uppercase tracking-wide ${
            isWiki
              ? "bg-amber-50 text-amber-600"
              : "bg-stone-100 text-stone-500"
          }`}
        >
          {isWiki ? "wiki" : "vault"}
        </span>
      </div>
      {result.snippet && <Snippet html={result.snippet} />}
    </button>
  );
});

/* ── Main component ─────────────────────────────────────────────────── */
export const SearchPanel = memo(function SearchPanel({
  onClose,
}: {
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<VaultFilter>("all");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const openFile = useEditorStore((s) => s.openFile);

  const handleQuery = useCallback(
    (q: string) => {
      setQuery(q);

      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (!q.trim()) {
        setResults([]);
        return;
      }

      debounceRef.current = setTimeout(async () => {
        setLoading(true);
        try {
          const data = await search(q, filter, 25);
          setResults(data.results);
        } catch {
          setResults([]);
        } finally {
          setLoading(false);
        }
      }, 180);
    },
    [filter],
  );

  const handleSelect = useCallback(
    (path: string) => {
      openFile(path);
      onClose();
    },
    [openFile, onClose],
  );

  const handleFilterChange = useCallback(
    (f: VaultFilter) => {
      setFilter(f);
      // Re-run search with new filter
      if (query.trim()) {
        setLoading(true);
        search(query, f, 25)
          .then((d) => setResults(d.results))
          .catch(() => setResults([]))
          .finally(() => setLoading(false));
      }
    },
    [query],
  );

  const FILTERS: { label: string; value: VaultFilter }[] = [
    { label: "All", value: "all" },
    { label: "Vault", value: "clean" },
    { label: "Wiki", value: "wiki" },
  ];

  return (
    <div className="flex flex-col overflow-hidden">
      {/* Search input */}
      <div className="relative px-2 pb-2 pt-1">
        <input
          autoFocus
          type="text"
          value={query}
          onChange={(e) => handleQuery(e.target.value)}
          placeholder="Search..."
          className="w-full rounded-md border border-stone-200 bg-white px-3 py-1.5 text-sm text-stone-800 placeholder:text-stone-400 focus:border-stone-400 focus:outline-none"
        />
        {/* Spinner */}
        {loading && (
          <div className="absolute right-4 top-1/2 -translate-y-1/2">
            <div className="h-3 w-3 animate-spin rounded-full border border-stone-300 border-t-stone-600" />
          </div>
        )}
      </div>

      {/* Vault filter tabs */}
      <div className="flex gap-1 px-2 pb-2">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => handleFilterChange(f.value)}
            className={`rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
              filter === f.value
                ? "bg-stone-800 text-white"
                : "text-stone-500 hover:bg-stone-100 hover:text-stone-700"
            }`}
          >
            {f.label}
          </button>
        ))}
        <button
          onClick={onClose}
          className="ml-auto text-[11px] text-stone-400 hover:text-stone-600"
        >
          ✕
        </button>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto px-1">
        {!query.trim() && (
          <p className="px-2 py-3 text-[11px] text-stone-400">
            Type to search across all files
          </p>
        )}

        {query.trim() && !loading && results.length === 0 && (
          <p className="px-2 py-3 text-[11px] text-stone-400">
            No results for "{query}"
          </p>
        )}

        {results.map((r) => (
          <ResultRow key={r.path} result={r} onSelect={handleSelect} />
        ))}
      </div>
    </div>
  );
});
