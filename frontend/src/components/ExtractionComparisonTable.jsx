import React from "react";
import { COMPARISON_FIELDS } from "@/lib/extractionFields";
import FieldComparison from "@/components/FieldComparison";

/**
 * Renders the full field-by-field comparison table.
 * Each field shows per-source values, confidence, conflict indicators,
 * action buttons, and the proposed local value.
 */
export default function ExtractionComparisonTable({
  sources,
  reviewState,
  onUseSource,
  onManualChange,
  onLeaveBlank,
}) {
  const doneSources = sources.filter((s) => s.status === "done");

  return (
    <div className="space-y-4">
      {COMPARISON_FIELDS.map((field) => (
        <FieldComparison
          key={field.key}
          field={field}
          sources={doneSources}
          reviewState={reviewState[field.key]}
          onUseSource={onUseSource}
          onManualChange={onManualChange}
          onLeaveBlank={onLeaveBlank}
        />
      ))}
    </div>
  );
}