import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { ErrorList, LoadingBlock } from "@/components/PageState";
import PasswordInput from "@/components/PasswordInput";

const PROVIDER_NAMES = { openai: "OpenAI", anthropic: "Anthropic", fake: "Demo extractor" };

// The user's own AI extraction provider. The saved API key never comes back from
// the server; only its last four characters are shown.
export default function AISettingsCard() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["ai-settings"], queryFn: () => api.get("/api/account/ai") });
  const [form, setForm] = React.useState(null);
  const [errors, setErrors] = React.useState(null);

  React.useEffect(() => {
    if (data) setForm({ provider: data.provider, model: data.model || "", api_key: "" });
  }, [data]);

  const onSaved = (view) => {
    queryClient.setQueryData(["ai-settings"], view);
    queryClient.invalidateQueries({ queryKey: ["config"] });
  };
  const save = useMutation({
    mutationFn: () => api.put("/api/account/ai", {
      provider: form.provider,
      model: form.model.trim() || null,
      api_key: form.api_key.trim() || null,
    }),
    onSuccess: (view) => { setErrors(null); onSaved(view); toast({ title: "AI settings saved" }); },
    onError: (err) => setErrors(err.errors?.length ? err.errors : [err.message]),
  });
  const test = useMutation({
    mutationFn: () => api.post("/api/account/ai/test"),
    onSuccess: (r) => { setErrors(null); toast({ title: "Connection works", description: `${PROVIDER_NAMES[r.provider] || r.provider} · ${r.model}` }); },
    onError: (err) => setErrors(err.errors?.length ? err.errors : [err.message]),
  });

  if (isLoading || !form) return <LoadingBlock />;

  const own = form.provider === "openai" || form.provider === "anthropic";
  // A saved key only carries over when the provider is unchanged.
  const keySaved = own && data.provider === form.provider && data.key_last4;
  const server = data.server_default;
  const serverLabel = server ? `${PROVIDER_NAMES[server.provider] || server.provider} · ${server.model}` : "no AI";
  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const changeProvider = (v) => setForm((f) => ({
    ...f, provider: v, api_key: "",
    model: v === data.provider ? data.model || "" : data.suggested_models[v]?.[0] || "",
  }));

  return (
    <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }}
      className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wide flex items-center gap-2">
        <Sparkles className="w-4 h-4" /> AI extraction
      </h2>
      <div className="space-y-2">
        <Label>Provider</Label>
        <Select value={form.provider} onValueChange={changeProvider}>
          <SelectTrigger className="h-11"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="default">Server default ({serverLabel})</SelectItem>
            <SelectItem value="openai">OpenAI — my own API key</SelectItem>
            <SelectItem value="anthropic">Anthropic — my own API key</SelectItem>
            <SelectItem value="none">Off — no AI extraction</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {own && (
        <>
          <div className="space-y-2">
            <Label htmlFor="ai-model">Model</Label>
            <Input id="ai-model" list="ai-models" required value={form.model}
              onChange={(e) => update("model", e.target.value)} className="h-11 text-base" />
            <datalist id="ai-models">
              {(data.suggested_models[form.provider] || []).map((m) => <option key={m} value={m} />)}
            </datalist>
          </div>
          <div className="space-y-2">
            <Label htmlFor="ai-key">API key</Label>
            <PasswordInput id="ai-key" autoComplete="off" required={!keySaved}
              placeholder={keySaved ? `Saved key ending in ${data.key_last4} — leave empty to keep it` : ""}
              value={form.api_key} onChange={(e) => update("api_key", e.target.value)} className="h-11 text-base" />
            <p className="text-xs text-slate-400">
              Usage is billed to your {PROVIDER_NAMES[form.provider]} account. The key is checked with the provider,
              stored encrypted, and never shown again.
            </p>
          </div>
        </>
      )}
      {!data.can_store_keys && own && (
        <p className="text-xs text-amber-700">This server has no SECRETS_KEY yet, so API keys cannot be saved. Ask the administrator.</p>
      )}
      <ErrorList errors={errors} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={save.isPending} className="bg-teal-600 hover:bg-teal-700">
          {save.isPending ? "Checking…" : "Save"}
        </Button>
        {data.provider !== "none" && (data.provider !== "default" || server) && (
          <Button type="button" variant="outline" disabled={test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? "Testing…" : "Test saved settings"}
          </Button>
        )}
      </div>
    </form>
  );
}
