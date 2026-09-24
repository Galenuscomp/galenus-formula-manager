import React from "react";
import { ChevronDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

export default function SourceMultiSelect({ value = [], onChange, options = [] }) {
  const [open, setOpen] = React.useState(false);

  const toggle = (option) => {
    if (value.includes(option)) {
      onChange(value.filter((v) => v !== option));
    } else {
      onChange([...value, option]);
    }
  };

  const label =
    value.length === 0
      ? "Select sources..."
      : value.length <= 2
        ? value.join(", ")
        : `${value.length} sources selected`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          className="w-full justify-between font-normal h-10"
        >
          <span className="truncate">{label}</span>
          <ChevronDown className="w-4 h-4 opacity-50 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="p-0 w-72" align="start">
        <div className="max-h-60 overflow-auto p-1">
          {options.map((option) => {
            const checked = value.includes(option);
            return (
              <div
                key={option}
                className="flex items-center gap-2.5 px-2.5 py-2 rounded-md hover:bg-slate-50 cursor-pointer select-none"
                onClick={() => toggle(option)}
              >
                <Checkbox checked={checked} className="pointer-events-none" />
                <span className="text-sm text-slate-700">{option}</span>
              </div>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}