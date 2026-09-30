import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Mail, XCircle } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";

// Admin: whether e-mail notifications are set up, and a test e-mail to themselves.
export default function MailCard() {
  const { data } = useQuery({ queryKey: ["mail-status"], queryFn: () => api.get("/api/users/mail") });
  const [result, setResult] = React.useState(null);
  const test = useMutation({
    mutationFn: () => api.post("/api/users/mail/test"),
    onSuccess: (r) => setResult({ ok: true, text: `Test e-mail sent to ${r.to}. Check the inbox (and spam).` }),
    onError: (err) => setResult({ ok: false, text: err.message }),
  });
  if (!data) return null;

  return (
    <section className="mt-8 rounded-xl border border-slate-200 bg-white p-5 space-y-3">
      <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide flex items-center gap-2">
        <Mail className="w-4 h-4" /> E-mail notifications
      </h2>
      <p className="text-sm text-slate-600">
        {data.enabled
          ? <>Sending as <span className="font-mono text-xs" dir="ltr">{data.from}</span>: invitations, password resets,
            password-change alerts, drafts awaiting approval and pharmacist decisions.</>
          : "Not set up: add RESEND_API_KEY to the server's .env to send invitations, resets and approval notices by e-mail."}
      </p>
      {result && (
        <p className={`text-sm flex items-start gap-1.5 ${result.ok ? "text-emerald-700" : "text-rose-700"}`}>
          {result.ok ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" /> : <XCircle className="w-4 h-4 mt-0.5 shrink-0" />}
          {result.text}
        </p>
      )}
      <Button variant="outline" onClick={() => test.mutate()} disabled={test.isPending}>
        {test.isPending ? "Sending…" : "Send me a test e-mail"}
      </Button>
    </section>
  );
}
