/**
 * EditorPanel — CodeMirror 6 markdown editor with React.memo isolation.
 *
 * Wraps useCodemirror hook; shows file path breadcrumb and
 * dirty/read-only indicators. Completely isolated from graph re-renders.
 */

import { memo, useCallback } from "react";
import { useEditorStore } from "@/stores/editorStore";
import { useCodemirror } from "./useCodemirror";

export const EditorPanel = memo(function EditorPanel() {
  const activeFilePath = useEditorStore((s) => s.activeFilePath);
  const fileContent = useEditorStore((s) => s.fileContent);
  const isReadOnly = useEditorStore((s) => s.isReadOnly);
  const isDirty = useEditorStore((s) => s.isDirty);
  const isLoading = useEditorStore((s) => s.isLoading);
  const updateContent = useEditorStore((s) => s.updateContent);
  const saveFile = useEditorStore((s) => s.saveFile);

  const handleChange = useCallback(
    (value: string) => {
      updateContent(value);
    },
    [updateContent],
  );

  const { setContainer } = useCodemirror({
    content: fileContent ?? "",
    readOnly: isReadOnly,
    onChange: handleChange,
  });

  // Ctrl/Cmd+S save handler
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        saveFile();
      }
    },
    [saveFile],
  );

  if (!activeFilePath) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-stone-400">
        Select a file to edit
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-stone-400">
        Loading...
      </div>
    );
  }

  // Extract display name from path
  const fileName = activeFilePath.split("/").pop() || activeFilePath;
  const parentPath = activeFilePath.split("/").slice(0, -1).join("/");

  return (
    <div className="flex flex-1 flex-col overflow-hidden" onKeyDown={handleKeyDown}>
      {/* Breadcrumb bar */}
      <div className="flex items-center gap-2 border-b border-stone-100 px-3 py-1.5 text-xs">
        <span className="text-stone-400 truncate max-w-[200px]">{parentPath}/</span>
        <span className="font-medium text-stone-700">{fileName}</span>
        {isReadOnly && (
          <span className="rounded bg-stone-100 px-1.5 py-0.5 text-[10px] font-medium text-stone-500">
            READ ONLY
          </span>
        )}
        {isDirty && (
          <span className="h-1.5 w-1.5 rounded-full bg-amber-400" title="Unsaved changes" />
        )}
      </div>

      {/* Editor container */}
      <div ref={setContainer} className="flex-1 overflow-hidden" />
    </div>
  );
});
