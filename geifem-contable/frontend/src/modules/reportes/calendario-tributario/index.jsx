import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";

const ESTILO_ESTADO = {
  vencida: "bg-red-100 text-red-700",
  proxima: "bg-geifem-gold/20 text-geifem-gold-dark",
  futura: "bg-slate-100 text-slate-600",
  verificar: "bg-blue-50 text-geifem-blue",
};

const ETIQUETA_ESTADO = {
  vencida: "Vencida",
  proxima: "Próxima",
  futura: "Futura",
  verificar: "Verificar municipio",
};

export default function Page() {
  const anioActual = new Date().getFullYear();
  const [anio, setAnio] = useState(anioActual);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  const generar = async (a) => {
    setError(null);
    setCargando(true);
    try {
      const { data } = await api.get(`/api/reportes/calendario-tributario?anio=${a}`);
      setData(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    generar(anioActual);
  }, []);

  return (
    <div>
      <p className="text-sm text-geifem-blue mb-1">
        <Link to="/reportes">Reportes</Link> › <Link to="/reportes/fiscales">Fiscales</Link>
      </p>
      <h1 className="text-2xl font-bold text-geifem-navy">Calendario tributario</h1>
      <p className="text-slate-500 mb-4">
        Fechas límite de las obligaciones fiscales calculadas según el NIT y el régimen tributario
        de la empresa activa.
      </p>

      <div className="flex items-end gap-3 mb-4 flex-wrap">
        <label className="text-sm text-slate-600">
          Año
          <select
            value={anio}
            onChange={(e) => {
              const a = Number(e.target.value);
              setAnio(a);
              generar(a);
            }}
            className="block border border-slate-300 rounded px-3 py-2 text-sm mt-1"
          >
            {[anioActual - 1, anioActual, anioActual + 1].map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </label>
        {cargando && <span className="text-sm text-slate-500">Generando…</span>}
      </div>

      {error && <div className="text-red-600 text-sm mb-3">{error}</div>}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 mb-4">
            <div className="bg-white border border-slate-200 rounded-lg p-3">
              <p className="text-xs uppercase text-slate-500">Empresa</p>
              <p className="text-sm font-semibold text-geifem-navy">
                {data.empresa.razon_social || "—"}
              </p>
              <p className="text-xs text-slate-500">
                NIT {data.empresa.nit || "—"} · Régimen {data.empresa.regimen}
              </p>
            </div>
            <div className="bg-white border border-slate-200 rounded-lg p-3">
              <p className="text-xs uppercase text-slate-500">Obligaciones del año</p>
              <p className="text-lg font-semibold text-geifem-navy">{data.resumen.total}</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-lg p-3">
              <p className="text-xs uppercase text-slate-500">Próximas 30 días</p>
              <p className="text-lg font-semibold text-geifem-gold-dark">
                {data.resumen.proximas_30_dias}
              </p>
            </div>
            <div className="bg-white border border-slate-200 rounded-lg p-3">
              <p className="text-xs uppercase text-slate-500">Vencidas</p>
              <p className="text-lg font-semibold text-red-600">{data.resumen.vencidas}</p>
            </div>
          </div>

          {data.proxima_fecha && (
            <div className="bg-geifem-gold/10 border border-geifem-gold/40 rounded-lg p-3 mb-4 text-sm">
              <span className="font-semibold text-geifem-navy">Próximo vencimiento: </span>
              {data.proxima_fecha.obligacion} — {data.proxima_fecha.periodo} — vence el{" "}
              {data.proxima_fecha.fecha_limite} ({data.proxima_fecha.dias} días)
            </div>
          )}

          <Table
            columns={[
              { key: "obligacion", label: "Obligación" },
              { key: "periodo", label: "Periodo" },
              { key: "fecha_limite", label: "Fecha límite" },
              {
                key: "estado",
                label: "Estado",
                render: (r) => (
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${ESTILO_ESTADO[r.estado] || "bg-slate-100 text-slate-600"}`}
                  >
                    {ETIQUETA_ESTADO[r.estado] || r.estado}
                  </span>
                ),
              },
              {
                key: "dias",
                label: "Días",
                render: (r) =>
                  r.dias == null ? "—" : r.dias < 0 ? `${Math.abs(r.dias)} atrás` : r.dias,
              },
            ]}
            rows={data.filas}
            empty="Sin obligaciones para el año seleccionado"
          />

          <p className="text-xs text-slate-400 mt-3">{data.nota}</p>
        </>
      )}
    </div>
  );
}
