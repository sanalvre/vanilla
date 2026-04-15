/**
 * ArticlePreview — shows the raw markdown content of a staged article.
 *
 * Reads the file content from the staging directory via the sidecar's
 * /search endpoint is not useful here — we expose a dedicated endpoint
 * in Phase 6 for reading staging file content.
 *
 * For now we render the raw markdown in a monospace pane with basic
 * heading / bold highlighting via simple CSS. A full markdown renderer
 * is deferred to Phase 7 (content viewer).
 */

interface ArticlePreviewProps {
  content: string;
  onClose: () => void;
}

export function ArticlePreview({ content, onClose }: ArticlePreviewProps) {
  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-stone-200 px-4 py-2">
        <span className="text-sm font-medium text-stone-700">Article Preview</span>
        <button
          onClick={onClose}
          className="rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600"
          aria-label="Close preview"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-stone-700">
          {content}
        </pre>
      </div>
    </div>
  );
}
