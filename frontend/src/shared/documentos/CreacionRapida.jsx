import { useState } from "react";
import api from "../../core/api.js";
import { useEmpresa } from "../../core/EmpresaContext.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import Modal from "../layout/Modal/index.jsx";
import FormField, { Input, Select } from "../layout/FormField/index.jsx";
import { mensajeError } from "./index.jsx";

/**
 * Crear sin salir del documento: cliente/tercero, producto o servicio y resolución DIAN.
 * Cada diálogo guarda en el catálogo real y devuelve el registro creado con `onCreado`.
 */
function Dialogo({ open, titulo, onClose, onGuardar, children, guardando, error }) {
  return (
    <Modal
      open={open} onClose={onClose} title={titulo}
      footer={<>
        <button onClick={onClose} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
        <button onClick={onGuardar} disabled={guardando} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white disabled:opacity-50">
          {guardando ? "Guardando…" : "Crear y usar"}
        </button>
      </>}
    >
      {children}
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
    </Modal>
  );
}

function useCrear(endpoint, onCreado, onClose) {
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const crear = async (cuerpo, validar) => {
    setError(null);
    const problema = validar?.();
    if (problema) return setError(problema);
    setGuardando(true);
    try {
      const { data } = await api.post(endpoint, cuerpo);
      onCreado(data);
      onClose();
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setGuardando(false);
    }
  };
  return { error, guardando, crear };
}

export function NuevoTerceroModal({ open, onClose, onCreado, tipo = "cliente" }) {
  const vacio = { tipo_documento: "CC", numero_documento: "", nombre: "", email: "", telefono: "", direccion: "", ciudad: "" };
  const [f, setF] = useState(vacio);
  const { error, guardando, crear } = useCrear("/api/configuracion/terceros", (d) => { setF(vacio); onCreado(d); }, onClose);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <Dialogo open={open} titulo={tipo === "cliente" ? "Nuevo cliente" : "Nuevo tercero"} onClose={onClose} guardando={guardando} error={error}
      onGuardar={() => crear({ ...f, tipo, tipo_persona: f.tipo_documento === "NIT" ? "juridica" : "natural", regimen: "ORDINARIO", responsable_iva: true },
        () => (!f.nombre.trim() ? "El nombre es obligatorio" : !f.numero_documento.trim() ? "El número de documento es obligatorio" : null))}>
      <div className="grid grid-cols-3 gap-3">
        <FormField label="Tipo de documento">
          <Select value={f.tipo_documento} onChange={set("tipo_documento")}>
            {["CC", "NIT", "CE", "PA", "TI"].map((x) => <option key={x}>{x}</option>)}
          </Select>
        </FormField>
        <div className="col-span-2"><FormField label="Número" hint={f.tipo_documento === "NIT" ? "Sin dígito de verificación: se calcula solo" : ""}><Input value={f.numero_documento} onChange={set("numero_documento")} /></FormField></div>
      </div>
      <FormField label="Nombre o razón social"><Input value={f.nombre} onChange={set("nombre")} /></FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Correo (para enviar la factura)"><Input type="email" value={f.email} onChange={set("email")} /></FormField>
        <FormField label="Teléfono"><Input value={f.telefono} onChange={set("telefono")} /></FormField>
        <FormField label="Dirección"><Input value={f.direccion} onChange={set("direccion")} /></FormField>
        <FormField label="Ciudad"><Input value={f.ciudad} onChange={set("ciudad")} /></FormField>
      </div>
      <p className="text-xs text-slate-500">El perfil tributario (régimen, retenciones) se completa luego en Configuración › Terceros.</p>
    </Dialogo>
  );
}

export function NuevoProductoModal({ open, onClose, onCreado }) {
  const { perfil } = useEmpresa();
  const vacio = { sku: "", nombre: "", precio_venta: "", tarifa_iva: "19", inventariable: true };
  const [f, setF] = useState(vacio);
  const { error, guardando, crear } = useCrear("/api/inventario/catalogo-productos", (d) => { setF(vacio); onCreado(d); }, onClose);
  const cobraIva = perfil?.cobra_iva !== false;
  return (
    <Dialogo open={open} titulo="Nuevo producto o servicio" onClose={onClose} guardando={guardando} error={error}
      onGuardar={() => crear({
        sku: f.sku.trim(), nombre: f.nombre.trim(), precio_venta: Number(f.precio_venta || 0), inventariable: f.inventariable,
        tipo_iva: "gravado", tarifa_iva: cobraIva ? Number(f.tarifa_iva) : 0,
      }, () => (!f.sku.trim() ? "El código es obligatorio" : !f.nombre.trim() ? "El nombre es obligatorio" : null))}>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Código (SKU)"><Input value={f.sku} onChange={(e) => setF({ ...f, sku: e.target.value })} /></FormField>
        <FormField label="Precio de venta"><Input type="number" value={f.precio_venta} onChange={(e) => setF({ ...f, precio_venta: e.target.value })} /></FormField>
      </div>
      <FormField label="Nombre"><Input value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></FormField>
      <div className="grid grid-cols-2 gap-3">
        {cobraIva && (
          <FormField label="IVA">
            <Select value={f.tarifa_iva} onChange={(e) => setF({ ...f, tarifa_iva: e.target.value })}>
              <option value="19">19 %</option><option value="5">5 %</option><option value="0">0 %</option>
            </Select>
          </FormField>
        )}
        <label className="flex items-center gap-2 text-sm pt-6">
          <input type="checkbox" checked={f.inventariable} onChange={(e) => setF({ ...f, inventariable: e.target.checked })} />
          Controla inventario (desmárcalo para servicios)
        </label>
      </div>
      <p className="text-xs text-slate-500">Nace con las cuentas de ingreso, inventario y costo de la empresa; puedes cambiarlas, y agregar retenciones e impuesto al consumo, en Inventario › Productos.</p>
    </Dialogo>
  );
}

export function NuevaResolucionModal({ open, onClose, onCreado }) {
  const hoyAnio = new Date().getFullYear();
  const vacio = { numero_resolucion: "", prefijo: "", rango_desde: "", rango_hasta: "", fecha_inicio: `${hoyAnio}-01-01`, fecha_fin: `${hoyAnio + 1}-12-31`, clave_tecnica: "" };
  const [f, setF] = useState(vacio);
  const { error, guardando, crear } = useCrear("/api/configuracion/resoluciones-dian", (d) => { setF(vacio); onCreado(d); }, onClose);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <Dialogo open={open} titulo="Nueva resolución de facturación" onClose={onClose} guardando={guardando} error={error}
      onGuardar={() => crear({ ...f, rango_desde: Number(f.rango_desde), rango_hasta: Number(f.rango_hasta), clave_tecnica: f.clave_tecnica || null, tipo_documento: "01" },
        () => (!f.numero_resolucion.trim() || !f.prefijo.trim() || !f.rango_desde || !f.rango_hasta ? "Completa resolución, prefijo y rango" : null))}>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Número de resolución"><Input value={f.numero_resolucion} onChange={set("numero_resolucion")} /></FormField>
        <FormField label="Prefijo"><Input value={f.prefijo} onChange={set("prefijo")} /></FormField>
        <FormField label="Rango desde"><Input type="number" value={f.rango_desde} onChange={set("rango_desde")} /></FormField>
        <FormField label="Rango hasta"><Input type="number" value={f.rango_hasta} onChange={set("rango_hasta")} /></FormField>
        <FormField label="Vigente desde"><Input type="date" value={f.fecha_inicio} onChange={set("fecha_inicio")} /></FormField>
        <FormField label="Vigente hasta"><Input type="date" value={f.fecha_fin} onChange={set("fecha_fin")} /></FormField>
      </div>
      <FormField label="Clave técnica (opcional)"><Input value={f.clave_tecnica} onChange={set("clave_tecnica")} /></FormField>
    </Dialogo>
  );
}

/** Botón «+ Nuevo» pequeño que acompaña a una lista desplegable; se oculta si el usuario no puede crear. */
export function BotonNuevo({ modulo, onClick, etiqueta = "+ Nuevo" }) {
  const { puede } = useAuth();
  if (!puede(modulo, "crear")) return null;
  return (
    <button type="button" onClick={onClick} className="text-xs text-geifem-blue hover:underline mt-1">{etiqueta}</button>
  );
}
