import { CheckCircle2, Circle } from "lucide-react";
import { passwordRules } from "@/lib/passwordRules";
import { cn } from "@/lib/utils";

// Live checklist under a new-password field.
export default function PasswordRules({ password, email }) {
  return (
    <ul className="space-y-1" aria-label="Password requirements">
      {passwordRules(password, email).map((r) => (
        <li key={r.label} className={cn("flex items-center gap-1.5 text-xs", r.ok ? "text-teal-700" : "text-slate-400")}>
          {r.ok ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Circle className="w-3.5 h-3.5" />}
          {r.label}
        </li>
      ))}
      <li className="text-xs text-slate-400 pt-1">Tip: a short sentence you will remember works well, e.g. four words and a number.</li>
    </ul>
  );
}
