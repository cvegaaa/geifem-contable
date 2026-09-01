"""Plan Único de Cuentas (PUC).

Alimentado por el módulo `configuracion/plan-cuentas`. Provee semillas mínimas
por régimen tributario para nuevas empresas. La estructura completa se
personaliza por empresa desde la UI.
"""
from .seed import puc_semilla

__all__ = ["puc_semilla"]
