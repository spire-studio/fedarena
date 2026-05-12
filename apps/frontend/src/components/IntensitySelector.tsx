const OPTIONS = [
  { value: 1, label: "Quick", desc: "1 seed, fast results" },
  { value: 0, label: "Standard", desc: "Matrix default seeds" },
  { value: 3, label: "Full", desc: "3 seeds, more reliable" },
];

interface Props {
  value: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}

export default function IntensitySelector({ value, onChange, disabled }: Props) {
  return (
    <div>
      <label className="block text-sm text-slate-400 mb-1">Evaluation Intensity</label>
      <div className="flex gap-1.5">
        {OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            disabled={disabled}
            className={`flex-1 py-1.5 px-2 rounded-md text-xs font-medium transition-colors disabled:opacity-50 ${
              value === opt.value
                ? "bg-blue-600/20 text-blue-400 border border-blue-600/40"
                : "bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600"
            }`}
            title={opt.desc}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-600 mt-1">
        {OPTIONS.find((o) => o.value === value)?.desc}
      </p>
    </div>
  );
}
