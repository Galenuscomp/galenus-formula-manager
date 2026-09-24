import React from "react";
import { cn } from "@/lib/utils";
import { SOURCE_LABELS } from "@/lib/sources";

export default function SourceLabel({ source, className }) {
  const config = SOURCE_LABELS[source] || SOURCE_LABELS["Other"];
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border whitespace-nowrap",
        config.className,
        className
      )}
    >
      {source || "Unknown"}
    </span>
  );
}