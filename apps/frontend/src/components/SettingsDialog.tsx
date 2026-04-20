import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Settings, X, Loader2 } from "lucide-react";
import { api } from "../api/client";

export default function SettingsDialog() {
  const [open, setOpen] = useState(false);
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSaved(false);
    api.getAgentConfig().then((c) => {
      setApiBase(c.api_base);
      setModel(c.model);
      setHasKey(c.has_api_key);
      setApiKey("");
    });
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, string> = {};
      if (apiBase) payload.api_base = apiBase;
      if (model) payload.model = model;
      if (apiKey) payload.api_key = apiKey;
      const updated = await api.updateAgentConfig(payload);
      setHasKey(updated.has_api_key);
      setApiBase(updated.api_base);
      setModel(updated.model);
      setApiKey("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button title="LLM Settings" className="p-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors">
          <Settings className="w-4 h-4" />
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-slate-900 border border-slate-700 rounded-xl p-6 z-50 shadow-2xl">
          <div className="flex items-center justify-between mb-5">
            <Dialog.Title className="text-lg font-semibold text-slate-50">LLM Settings</Dialog.Title>
            <Dialog.Close asChild>
              <button className="p-1 text-slate-400 hover:text-slate-200"><X className="w-4 h-4" /></button>
            </Dialog.Close>
          </div>

          <div className="space-y-4">
            <Field label="API Base URL">
              <input
                value={apiBase}
                onChange={(e) => setApiBase(e.target.value)}
                placeholder="https://api.openai.com/v1"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500"
              />
            </Field>

            <Field label="Model">
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="gpt-4o"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500"
              />
            </Field>

            <Field label={`API Key${hasKey ? " (already set)" : ""}`}>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={hasKey ? "Leave blank to keep current key" : "sk-..."}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500"
              />
            </Field>
          </div>

          <div className="flex items-center justify-end gap-3 mt-6">
            {saved && <span className="text-sm text-green-400">Saved</span>}
            <Dialog.Close asChild>
              <button className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200">Cancel</button>
            </Dialog.Close>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white rounded-md text-sm font-medium transition-colors flex items-center gap-2"
            >
              {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Save
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm text-slate-400 mb-1">{label}</label>
      {children}
    </div>
  );
}
