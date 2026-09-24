import React from "react";
import { cn } from "@/lib/utils";
import SourceLabel from "@/components/SourceLabel";

/**
 * Ingredient-by-ingredient comparison across all extracted sources.
 * Highlights missing ingredients and quantity/unit/role differences.
 * Does NOT merge ingredients automatically.
 */
export default function IngredientComparison({ sources }) {
  // Build union of ingredient names (case-insensitive matching)
  const ingredientNames = [];
  const nameMap = {};

  sources.forEach((s) => {
    const ings = s.data?.ingredients;
    if (!Array.isArray(ings)) return;
    ings.forEach((ing) => {
      if (!ing?.ingredient_name) return;
      const lower = ing.ingredient_name.trim().toLowerCase();
      if (!nameMap[lower]) {
        nameMap[lower] = ing.ingredient_name.trim();
        ingredientNames.push(lower);
      }
    });
  });

  if (ingredientNames.length === 0) {
    return (
      <p className="text-sm text-slate-400 italic mb-3">
        No ingredients found in any source document
      </p>
    );
  }

  return (
    <div className="mb-3 overflow-x-auto rounded-md border border-slate-200">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className="text-left py-2 px-3 font-medium text-slate-700">Ingredient</th>
            {sources.map((s) => (
              <th key={s.formulaId} className="text-left py-2 px-3 font-medium text-slate-700 min-w-[140px]">
                <SourceLabel source={s.sourceName} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ingredientNames.map((lowerName) => {
            const displayName = nameMap[lowerName];
            const matches = sources.map((s) => {
              const ings = s.data?.ingredients || [];
              return ings.find((ing) => ing?.ingredient_name?.trim().toLowerCase() === lowerName);
            });

            const present = matches.filter(Boolean);
            const quantities = present.map((m) => (m.quantity || "").trim()).filter(Boolean);
            const roles = present.map((m) => (m.function || m.role || "").trim()).filter(Boolean);
            const qtyDiff = new Set(quantities.map((q) => q.toLowerCase())).size > 1;
            const roleDiff = new Set(roles.map((r) => r.toLowerCase())).size > 1;
            const isMissingInSome = matches.some((m) => !m);
            const hasIssue = qtyDiff || roleDiff || isMissingInSome;

            return (
              <tr key={lowerName} className="border-b border-slate-100 last:border-0">
                <td className={cn("py-2 px-3 font-medium", hasIssue ? "text-amber-800" : "text-slate-900")}>
                  {displayName}
                  {isMissingInSome && (
                    <span className="ml-2 text-xs text-rose-500">missing in source(s)</span>
                  )}
                </td>
                {matches.map((m, i) => (
                  <td key={i} className="py-2 px-3 align-top">
                    {!m ? (
                      <span className="text-rose-500 text-xs italic">Missing</span>
                    ) : (
                      <div className="space-y-0.5">
                        <div className={cn(qtyDiff && "text-amber-700 font-medium")}>
                          {m.quantity || "—"}{m.unit ? ` ${m.unit}` : ""}
                          {qtyDiff && <span className="ml-1 text-xs text-amber-600">⚠</span>}
                        </div>
                        {(m.function || m.role) && (
                          <div className={cn("text-xs text-slate-500", roleDiff && "text-amber-600 font-medium")}>
                            {m.function || m.role}
                            {roleDiff && <span className="ml-1">⚠</span>}
                          </div>
                        )}
                      </div>
                    )}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}