const STATUS_CONFIG = {
  Queued: { label: "Waiting to start", progress: 10, tone: "slate" },
  Running: { label: "Working…", progress: 55, tone: "blue" },
  Completed: { label: "Completed", progress: 100, tone: "emerald" },
  "No results": { label: "No matching formulas found", progress: 100, tone: "amber" },
  Failed: { label: "Failed", progress: 100, tone: "rose" },
  Cooldown: { label: "Rate limited — retry shortly", progress: 100, tone: "amber" },
  Cancelled: { label: "Cancelled", progress: 100, tone: "slate" },
};

const TONE_CLASSES = {
  slate: { badge: "bg-slate-100 text-slate-600 border-slate-200", bar: "bg-slate-400" },
  blue: { badge: "bg-blue-50 text-blue-700 border-blue-200", bar: "bg-blue-500" },
  emerald: { badge: "bg-emerald-50 text-emerald-700 border-emerald-200", bar: "bg-emerald-500" },
  amber: { badge: "bg-amber-50 text-amber-700 border-amber-200", bar: "bg-amber-500" },
  rose: { badge: "bg-rose-50 text-rose-700 border-rose-200", bar: "bg-rose-500" },
};

export function getJobStatusConfig(status) {
  return STATUS_CONFIG[status] || STATUS_CONFIG.Queued;
}

export function getJobToneClasses(tone) {
  return TONE_CLASSES[tone] || TONE_CLASSES.slate;
}

export const isJobActive = (status) => status === "Queued" || status === "Running";
export const isJobRetryable = (status) => ["Failed", "Cooldown", "No results", "Cancelled"].includes(status);
