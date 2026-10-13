// Valor en letras (formato colombiano). Misma lógica que backend/core/letras.py.
const UNIDADES = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece",
  "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós",
  "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"];
const DECENAS = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"];
const CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos"];

function menorMil(n) {
  if (n === 0) return "";
  if (n === 100) return "cien";
  const c = Math.floor(n / 100);
  const resto = n % 100;
  const partes = c ? [CENTENAS[c]] : [];
  if (resto < 30) {
    if (resto) partes.push(UNIDADES[resto]);
  } else {
    const d = Math.floor(resto / 10);
    const u = resto % 10;
    partes.push(DECENAS[d] + (u ? ` y ${UNIDADES[u]}` : ""));
  }
  return partes.join(" ");
}

function apocopar(t) {
  if (t.endsWith("veintiuno")) return `${t.slice(0, -"veintiuno".length)}veintiún`;
  if (t === "uno" || t.endsWith(" uno")) return `${t.slice(0, -3)}un`;
  return t;
}

export function enteroALetras(entero) {
  let n = Math.floor(Math.abs(entero));
  if (n === 0) return "cero";
  const partes = [];
  const billones = Math.floor(n / 1e12);
  n %= 1e12;
  if (billones) partes.push(billones === 1 ? "un billón" : `${apocopar(enteroALetras(billones))} billones`);
  const millones = Math.floor(n / 1e6);
  n %= 1e6;
  if (millones) partes.push(millones === 1 ? "un millón" : `${apocopar(enteroALetras(millones))} millones`);
  const miles = Math.floor(n / 1000);
  const resto = n % 1000;
  if (miles) partes.push(miles === 1 ? "mil" : `${apocopar(menorMil(miles))} mil`);
  if (resto) partes.push(menorMil(resto));
  return partes.join(" ");
}

/** «Son: dos millones cien mil pesos con cincuenta centavos M/CTE» */
export function valorEnLetras(valor, moneda = "pesos", sufijo = "M/CTE") {
  const total = Math.round(Math.abs(Number(valor) || 0) * 100);
  const pesos = Math.floor(total / 100);
  const centavos = total % 100;
  let texto = apocopar(enteroALetras(pesos));
  if (pesos && pesos % 1e6 === 0) texto += " de";
  let salida = `${texto} ${pesos === 1 ? "peso" : moneda}`;
  if (centavos) salida += ` con ${apocopar(enteroALetras(centavos))} centavo${centavos !== 1 ? "s" : ""}`;
  return `Son: ${salida} ${sufijo}`;
}
