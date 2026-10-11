/** Native range input dressed as a macOS slider. */
export function Slider({
  value,
  onChange,
  onCommit,
  label,
  min = 0,
  max = 1,
  step = 0.01,
}: {
  value: number;
  onChange: (v: number) => void;
  onCommit?: (v: number) => void;
  label: string;
  min?: number;
  max?: number;
  step?: number;
}) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <input
      type="range"
      aria-label={label}
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      onPointerUp={(e) => onCommit?.(Number((e.target as HTMLInputElement).value))}
      onKeyUp={(e) => onCommit?.(Number((e.target as HTMLInputElement).value))}
      className="sasu-slider h-5 w-full"
      style={{ "--pct": `${pct}%` } as React.CSSProperties}
    />
  );
}
