export default function FormField({ label, children, hint }) {
  return (
    <label className="block mb-3">
      <span className="block text-sm font-medium text-slate-700 mb-1">{label}</span>
      {children}
      {hint && <span className="block text-xs text-slate-500 mt-1">{hint}</span>}
    </label>
  );
}

export function Input(props) {
  return (
    <input
      {...props}
      className={`w-full border border-slate-300 rounded px-3 py-2 focus:ring-2 focus:ring-geifem-blue focus:outline-none ${props.className || ""}`}
    />
  );
}

export function Select({ children, ...rest }) {
  return (
    <select
      {...rest}
      className={`w-full border border-slate-300 rounded px-3 py-2 bg-white focus:ring-2 focus:ring-geifem-blue focus:outline-none ${rest.className || ""}`}
    >
      {children}
    </select>
  );
}
