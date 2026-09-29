import React from "react";
import { Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { formatDateTime } from "@/lib/utils";

// Shows a one-time invitation/reset link once, for the admin to send to the user.
export default function PasswordLinkDialog({ link, user, onClose }) {
  const url = link ? window.location.origin + link.path : "";
  const [copied, setCopied] = React.useState(false);
  React.useEffect(() => setCopied(false), [link]);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      /* clipboard blocked: the field is selectable */
    }
  };

  return (
    <Dialog open={!!link} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{link?.purpose === "invite" ? "Invitation link" : "Password reset link"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            Send this link to <span className="font-medium text-slate-900">{user?.email}</span> (e-mail, WhatsApp…).
            They open it and choose their own password. It works once and expires {link && formatDateTime(link.expires_at)}.
          </p>
          <div className="flex gap-2">
            <Input readOnly value={url} onFocus={(e) => e.target.select()} className="h-11 text-sm font-mono" />
            <Button type="button" onClick={copy} className="bg-teal-600 hover:bg-teal-700 shrink-0">
              <Copy className="w-4 h-4 mr-1.5" />{copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <p className="text-xs text-slate-400">
            The link is shown only now. If it gets lost, create a new one; the old link stops working.
          </p>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Done</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
