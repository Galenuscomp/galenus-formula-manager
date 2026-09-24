export const FORMULA_SOURCES = [
  "CompoundingToday",
  "MEDISCA",
  "USP",
  "Trissel's",
  "Allen's Compounded Formulations",
  "Scientific literature",
  "Internal pharmacy formula",
  "Other",
];

export const DEFAULT_SOURCES = ["CompoundingToday", "MEDISCA"];

export const AUTOMATED_SOURCES = ["CompoundingToday", "MEDISCA"];

export const SOURCE_LABELS = {
  "CompoundingToday": { className: "bg-teal-50 text-teal-700 border-teal-200" },
  "MEDISCA": { className: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  "USP": { className: "bg-blue-50 text-blue-700 border-blue-200" },
  "Trissel's": { className: "bg-violet-50 text-violet-700 border-violet-200" },
  "Allen's Compounded Formulations": { className: "bg-cyan-50 text-cyan-700 border-cyan-200" },
  "Scientific literature": { className: "bg-amber-50 text-amber-700 border-amber-200" },
  "Internal pharmacy formula": { className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  "Other": { className: "bg-slate-100 text-slate-600 border-slate-200" },
};

// Ordering: CompoundingToday and MEDISCA first, then remaining sources in order
export const SOURCE_ORDER = FORMULA_SOURCES;

export function sortSourcesByOrder(sources) {
  return [...sources].sort((a, b) => {
    const ia = SOURCE_ORDER.indexOf(a);
    const ib = SOURCE_ORDER.indexOf(b);
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
  });
}