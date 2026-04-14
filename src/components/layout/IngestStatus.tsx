/**
 * IngestStatus — shows active ingestion job progress in the sidebar.
 */

import { useState, useEffect, useCallback } from "react";
import { getIngestStatus } from "@/api/ingest";

interface IngestJob {
  jobId: string;
  label: string;
  status: "pending" | "processing" | "complete" | "error";
  progress: number;
  error?: string;
}

interface IngestStatusProps {
  jobs: IngestJob[];
  onJobComplete?: (jobId: string, outputPath: string) => void;
}

export function IngestStatus({ jobs, onJobComplete }: IngestStatusProps) {
  const [activeJobs, setActiveJobs] = useState<IngestJob[]>(jobs);

  // Poll active jobs for status updates
  useEffect(() => {
    if (activeJobs.length === 0) return;

    const pending = activeJobs.filter(
      (j) => j.status === "pending" || j.status === "processing",
    );
    if (pending.length === 0) return;

    const interval = setInterval(async () => {
      const updates = await Promise.all(
        pending.map(async (job) => {
          try {
            const status = await getIngestStatus(job.jobId);
            const updated = {
              ...job,
              status: status.status,
              progress: status.progress,
              error: status.error ?? undefined,
            };

            if (status.status === "complete" && status.output_path) {
              onJobComplete?.(job.jobId, status.output_path);
            }

            return updated;
          } catch {
            return job;
          }
        }),
      );

      setActiveJobs((prev) =>
        prev.map((j) => {
          const update = updates.find((u) => u.jobId === j.jobId);
          return update || j;
        }),
      );
    }, 2000);

    return () => clearInterval(interval);
  }, [activeJobs, onJobComplete]);

  // Sync external jobs prop
  useEffect(() => {
    setActiveJobs((prev) => {
      const existingIds = new Set(prev.map((j) => j.jobId));
      const newJobs = jobs.filter((j) => !existingIds.has(j.jobId));
      return [...prev, ...newJobs];
    });
  }, [jobs]);

  // Show non-complete jobs (pending/processing/error always visible)
  const visibleJobs = activeJobs.filter(
    (j) => j.status !== "complete",
  );

  if (visibleJobs.length === 0) return null;

  return (
    <div className="space-y-1 px-2 py-1">
      <p className="text-xs font-medium uppercase tracking-wider text-stone-400">
        Ingesting
      </p>
      {visibleJobs.map((job) => (
        <div key={job.jobId} className="text-xs">
          <div className="flex items-center justify-between">
            <span className="truncate text-stone-600">{job.label}</span>
            <span
              className={
                job.status === "error"
                  ? "text-red-500"
                  : job.status === "complete"
                    ? "text-green-600"
                    : "text-stone-400"
              }
            >
              {job.status === "processing"
                ? `${Math.round(job.progress * 100)}%`
                : job.status}
            </span>
          </div>
          {job.status === "processing" && (
            <div className="mt-0.5 h-1 w-full rounded bg-stone-200">
              <div
                className="h-1 rounded bg-amber-400 transition-all"
                style={{ width: `${job.progress * 100}%` }}
              />
            </div>
          )}
          {job.error && (
            <p className="mt-0.5 text-red-500">{job.error}</p>
          )}
        </div>
      ))}
    </div>
  );
}
