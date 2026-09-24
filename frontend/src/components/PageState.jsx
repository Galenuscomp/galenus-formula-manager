import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LoadingBlock() {
  return (
    <div className="p-8 flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-slate-200 border-t-teal-600 rounded-full animate-spin" />
    </div>
  );
}

export function ErrorBlock({ error, onRetry }) {
  return (
    <div className="m-4 rounded-lg bg-rose-50 border border-rose-200 p-4 flex items-start gap-2">
      <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 shrink-0" />
      <div className="flex-1">
        <p className="text-sm text-rose-800">{error?.message || "Something went wrong."}</p>
        {onRetry && (
          <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}

export function ErrorList({ errors }) {
  if (!errors?.length) return null;
  return (
    <div className="rounded-lg bg-rose-50 border border-rose-200 px-4 py-3 space-y-1">
      {errors.map((e, i) => (
        <p key={i} className="text-sm text-rose-700 flex items-start gap-1.5">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /> {e}
        </p>
      ))}
    </div>
  );
}
