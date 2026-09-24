import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import FormulaStatusBadge from "@/components/FormulaStatusBadge";
import { formatDate } from "@/lib/utils";

export default function RequestListItem({ req }) {
  const details = [req.strength, req.dosage_form, req.final_quantity].filter(Boolean).join(" · ");
  return (
    <li>
      <Link
        to={`/requests/${req.id}`}
        className="flex items-center gap-3 p-4 hover:bg-slate-50 active:bg-slate-100 transition-colors"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <p className="font-medium text-slate-900 truncate">{req.active_ingredient}</p>
            <span className="text-xs font-mono text-slate-400">{req.number}</span>
          </div>
          {details && <p className="text-sm text-slate-500 truncate">{details}</p>}
          <div className="mt-1.5 flex items-center gap-2 sm:hidden">
            <FormulaStatusBadge status={req.status} />
          </div>
        </div>
        <div className="hidden sm:flex flex-col items-end gap-1 shrink-0">
          <FormulaStatusBadge status={req.status} />
          <span className="text-xs text-slate-400">{formatDate(req.created_at)}</span>
        </div>
        <ChevronRight className="w-4 h-4 text-slate-300 shrink-0" />
      </Link>
    </li>
  );
}
