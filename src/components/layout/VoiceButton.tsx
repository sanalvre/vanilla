/**
 * VoiceButton — global voice transcription controller.
 *
 * Responds to three triggers:
 *   1. Tauri "voice:start" event  (Ctrl+Shift+Space pressed)
 *   2. Tauri "voice:stop" event   (Ctrl+Shift+Space released)
 *   3. "vanilla:voice-toggle" DOM event (mic button click in SidebarRail)
 *
 * Correct hold-to-talk flow:
 *   voice:start → POST /voice/start  (sidecar begins capturing audio NOW)
 *   voice:stop  → POST /voice/stop   (sidecar stops + transcribes → transcript)
 *
 * Transcript is delivered by dispatching "vanilla:voice-transcript" on window.
 * useCodemirror listens for that event and inserts the text at cursor.
 *
 * Does NOT render visible UI — the recording indicator lives in SidebarRail.
 */

import { useEffect, useRef } from "react";
import { useVoiceStore } from "@/stores/voiceStore";
import { startRecording, stopRecording } from "@/api/voice";

type UnlistenFn = () => void;

async function listenTauri(
  event: string,
  handler: () => void,
): Promise<UnlistenFn | null> {
  try {
    const { listen } = await import("@tauri-apps/api/event");
    return await listen(event, handler);
  } catch {
    // Not running inside Tauri (browser dev mode)
    return null;
  }
}

export function VoiceButton() {
  const { modelSize, setRecording, setTranscript, setError } = useVoiceStore();
  const isRecordingRef = useRef(false);
  // Keep modelSize accessible in callbacks without re-registering listeners
  const modelSizeRef = useRef(modelSize);
  modelSizeRef.current = modelSize;

  useEffect(() => {
    let unlistenStart: UnlistenFn | null = null;
    let unlistenStop: UnlistenFn | null = null;

    const onStart = async () => {
      if (isRecordingRef.current) return;
      isRecordingRef.current = true;
      setRecording(true);
      setError(null);
      try {
        // Tell sidecar to start capturing audio immediately
        await startRecording(modelSizeRef.current);
      } catch (e) {
        // Failed to start (e.g. deps not installed) — roll back state
        isRecordingRef.current = false;
        setRecording(false);
        const msg = e instanceof Error ? e.message : "Voice start failed";
        setError(msg);
        console.warn("[VoiceButton] start:", msg);
      }
    };

    const onStop = async () => {
      if (!isRecordingRef.current) return;
      isRecordingRef.current = false;
      setRecording(false);
      try {
        // Tell sidecar to stop capturing and transcribe whatever was recorded
        const { transcript } = await stopRecording();
        setTranscript(transcript);

        // Deliver to whatever input/editor is listening
        window.dispatchEvent(
          new CustomEvent("vanilla:voice-transcript", {
            detail: { transcript },
          }),
        );
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Voice transcription failed";
        setError(msg);
        console.warn("[VoiceButton] stop:", msg);
      }
    };

    // Button click in SidebarRail dispatches this to toggle recording
    const onToggle = () => {
      if (isRecordingRef.current) {
        onStop();
      } else {
        onStart();
      }
    };

    // Wire up Tauri event listeners (hotkey)
    Promise.all([
      listenTauri("voice:start", onStart),
      listenTauri("voice:stop", onStop),
    ]).then(([u1, u2]) => {
      unlistenStart = u1;
      unlistenStop = u2;
    });

    // Wire up button-click toggle from SidebarRail
    window.addEventListener("vanilla:voice-toggle", onToggle);

    return () => {
      unlistenStart?.();
      unlistenStop?.();
      window.removeEventListener("vanilla:voice-toggle", onToggle);
    };
  }, [setRecording, setTranscript, setError]); // modelSize handled via ref

  // No visible UI — indicator is in SidebarRail
  return null;
}
