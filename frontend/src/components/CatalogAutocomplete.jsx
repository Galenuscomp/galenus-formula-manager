import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api, qs } from "@/api/client";
import { Input } from "@/components/ui/input";
import SourceLabel from "@/components/SourceLabel";
import { useDebounced } from "@/lib/useDebounced";
import { cn } from "@/lib/utils";

// Text input that suggests formulas from the imported MEDISCA / CompoundingToday
// catalogs while typing. Typing freely still works; picking calls onPick(entry).
export default function CatalogAutocomplete({ id, value, onChange, onPick, className, ...props }) {
  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState(-1);
  const q = useDebounced(value.trim(), 200);
  const { data: hits = [], isFetching } = useQuery({
    queryKey: ["catalog-search", q],
    queryFn: () => api.get(`/api/catalog/search${qs({ q, limit: 10 })}`),
    enabled: open && q.length >= 2,
    staleTime: 5 * 60 * 1000,
    placeholderData: (prev) => prev,
  });
  const shown = open && value.trim().length >= 2 ? hits : [];
  const listId = `${id}-catalog`;

  const pick = (entry) => {
    onPick(entry);
    setOpen(false);
    setActive(-1);
  };
  const onKeyDown = (e) => {
    if (!shown.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => (i + 1) % shown.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => (i <= 0 ? shown.length - 1 : i - 1)); }
    else if (e.key === "Enter" && active >= 0) { e.preventDefault(); pick(shown[active]); }
    else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="relative">
      <Input id={id} value={value} autoComplete="off" role="combobox" aria-expanded={shown.length > 0}
        aria-controls={listId} aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        onChange={(e) => { onChange(e.target.value); setOpen(true); setActive(-1); }}
        onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown} className={className} {...props} />
      {isFetching && open && <Loader2 className="absolute right-3 top-3.5 w-4 h-4 animate-spin text-slate-300" />}
      {shown.length > 0 && (
        <ul id={listId} role="listbox"
          className="absolute z-30 mt-1 w-full md:w-[160%] max-h-80 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-lg py-1">
          {shown.map((h, i) => (
            <li key={h.id} id={`${listId}-${i}`} role="option" aria-selected={i === active}
              onMouseDown={(e) => { e.preventDefault(); pick(h); }} onMouseEnter={() => setActive(i)}
              className={cn("px-3 py-2 cursor-pointer", i === active ? "bg-teal-50" : "hover:bg-slate-50")}>
              <div className="flex items-start gap-2">
                <SourceLabel source={h.source} className="mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm text-slate-900 leading-snug">{h.title}</p>
                  <p className="text-xs text-slate-400">{[h.formula_id, h.base].filter(Boolean).join(" · ")}</p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
