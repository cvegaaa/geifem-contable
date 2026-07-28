import { useState } from "react";

/**
 * Logo GEIFEM. Renderiza /logo.png si el archivo está disponible en /public
 * (o en src/assets accesible como /logo.png). Si no, muestra un fallback
 * tipográfico con la marca. Así el proyecto no se rompe hasta que el
 * usuario suba el archivo oficial del logo.
 *
 * Props:
 *   variant: "full" | "mark"  — full = ícono + wordmark, mark = solo ícono
 *   theme:   "light" | "dark" — controla el color del wordmark de respaldo
 *   size:    px del alto del ícono (default 40)
 */
export default function Logo({ variant = "full", theme = "dark", size = 40 }) {
  const [broken, setBroken] = useState(false);

  const wordmarkColor = theme === "light" ? "text-white" : "text-geifem-navy";
  const sloganColor = theme === "light" ? "text-geifem-gold" : "text-geifem-blue";

  return (
    <div className="flex items-center gap-3">
      {!broken ? (
        <img
          src="/logo.png"
          alt="GEIFEM"
          style={{ height: size, width: "auto" }}
          onError={() => setBroken(true)}
          className="object-contain"
        />
      ) : (
        // Fallback: hexágono estilizado con la "G"
        <div
          style={{ height: size, width: size }}
          className="rounded-md bg-geifem-navy text-geifem-gold font-extrabold flex items-center justify-center"
        >
          <span style={{ fontSize: size * 0.55, lineHeight: 1 }}>G</span>
        </div>
      )}
      {variant === "full" && (
        <div className="leading-tight">
          <div className={`font-extrabold tracking-wide ${wordmarkColor}`}>
            GEIFEM
          </div>
          <div className={`text-[9px] uppercase tracking-wider ${sloganColor}`}>
            Contable
          </div>
        </div>
      )}
    </div>
  );
}
