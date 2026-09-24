import React from "react";
import { cn } from "@/lib/utils";

const statusConfig = {
  "New": { label: "New", className: "bg-slate-100 text-slate-700 border-slate-200" },
  "Searching": { label: "Searching", className: "bg-blue-50 text-blue-700 border-blue-200" },
  "Formula found": { label: "Formula found", className: "bg-teal-50 text-teal-700 border-teal-200" },
  "No formula found": { label: "No formula found", className: "bg-amber-50 text-amber-700 border-amber-200" },
  "Downloaded": { label: "Downloaded", className: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  "Draft created": { label: "Draft created", className: "bg-cyan-50 text-cyan-700 border-cyan-200" },
  "Pending pharmacist approval": { label: "Pending approval", className: "bg-violet-50 text-violet-700 border-violet-200" },
  "Approved": { label: "Approved Master Formula", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  "Rejected": { label: "Rejected", className: "bg-rose-50 text-rose-700 border-rose-200" },
  "Requires correction": { label: "Requires correction", className: "bg-orange-50 text-orange-700 border-orange-200" },
  "Error": { label: "Error", className: "bg-red-50 text-red-700 border-red-200" },
};

export default function FormulaStatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig["New"];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border whitespace-nowrap",
        config.className
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
      {config.label}
    </span>
  );
}