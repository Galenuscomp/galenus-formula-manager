import React from "react";
import { cn } from "@/lib/utils";

const functionConfig = {
  "active": { label: "Active ingredient", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  "additional active": { label: "Additional active", className: "bg-blue-50 text-blue-700 border-blue-200" },
  "primary": { label: "Active ingredient", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
};

const confidenceConfig = {
  "high": "bg-emerald-50 text-emerald-700",
  "medium": "bg-amber-50 text-amber-700",
  "low": "bg-rose-50 text-rose-600",
};

function safeDecode(s) {
  if (!s) return s;
  try { return decodeURIComponent(s); } catch { return s; }
}

export default function ActiveIngredientsTable({ activeIngredients = [] }) {
  if (!activeIngredients || activeIngredients.length === 0) {
    return (
      <p className="text-sm text-slate-400 italic">
        No active ingredients identified
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className="text-left py-2 px-3 font-medium text-slate-700">Active Ingredient</th>
            <th className="text-left py-2 px-3 font-medium text-slate-700">Salt Form</th>
            <th className="text-left py-2 px-3 font-medium text-slate-700">Strength</th>
            <th className="text-left py-2 px-3 font-medium text-slate-700">Unit</th>
            <th className="text-left py-2 px-3 font-medium text-slate-700">Function</th>
            <th className="text-left py-2 px-3 font-medium text-slate-700">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {activeIngredients.map((ai, i) => {
            const func = (ai.function || ai.role || "active").toLowerCase();
            const fc = functionConfig[func] || { label: func, className: "bg-slate-50 text-slate-600 border-slate-200" };
            const conf = (ai.source_confidence || "").toLowerCase();
            return (
              <tr key={i} className="border-b border-slate-100 last:border-0">
                <td className="py-2 px-3 font-medium text-slate-900">{safeDecode(ai.name) || "—"}</td>
                <td className="py-2 px-3 text-slate-600">{ai.salt_form || "—"}</td>
                <td className="py-2 px-3 text-slate-600">{ai.concentration || ai.strength || "—"}</td>
                <td className="py-2 px-3 text-slate-600">{ai.concentration_unit || ai.strength_unit || "—"}</td>
                <td className="py-2 px-3">
                  <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border", fc.className)}>
                    {fc.label}
                  </span>
                </td>
                <td className="py-2 px-3">
                  {conf && (
                    <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize", confidenceConfig[conf] || "bg-slate-50 text-slate-500")}>
                      {conf}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}