import { Loader2, RotateCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import SourceLabel from "@/components/SourceLabel";
import { getJobStatusConfig, getJobToneClasses, isJobActive, isJobRetryable } from "@/lib/sourceSearchJobs";
import { fromNow } from "@/lib/utils";

export default function SourceSearchJobCard({ job, onRetry, onCancel, busy }) {
  const config = getJobStatusConfig(job.status);
  const tones = getJobToneClasses(config.tone);
  const active = isJobActive(job.status);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex flex-wrap items-center gap-2">
          <SourceLabel source={job.source_name} />
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${tones.badge}`}>
            {active && <Loader2 className="w-3 h-3 animate-spin" />}
            {job.status === "Running" && job.source_name ? `Searching ${job.source_name}` : config.label}
          </span>
        </div>
        <span className="text-xs text-slate-400 whitespace-nowrap">{fromNow(job.finished_at || job.started_at || job.created_at)}</span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden mb-3">
        <div className={`h-full rounded-full transition-all duration-500 ${tones.bar} ${active ? "animate-pulse" : ""}`}
          style={{ width: `${config.progress}%` }} />
      </div>
      {job.error && (
        <p className={`text-xs mb-3 ${active ? "text-slate-500" : "text-rose-600"}`}>{job.error}</p>
      )}
      {job.attempts > 1 && <p className="text-xs text-slate-400 mb-3">Attempt {job.attempts} of {job.max_attempts}</p>}
      {(active || isJobRetryable(job.status)) && (
        <div className="flex gap-2">
          {isJobRetryable(job.status) && onRetry && (
            <Button variant="outline" size="sm" disabled={busy} onClick={() => onRetry(job)}>
              <RotateCcw className="w-3.5 h-3.5 mr-1" /> Retry search
            </Button>
          )}
          {active && onCancel && (
            <Button variant="outline" size="sm" disabled={busy} onClick={() => onCancel(job)}>
              <X className="w-3.5 h-3.5 mr-1" /> Cancel
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
