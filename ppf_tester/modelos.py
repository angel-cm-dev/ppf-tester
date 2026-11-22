"""Perfiles de teclados Yamaha PSR de la serie S y su memoria de expansión.

Fuentes: hojas de especificaciones de Yamaha y distribuidores (S670 ≈ 32 MB,
S770 160 MB, S970 512 MB, S775 280 MB, S975 768 MB).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Modelo:
    nombre: str
    memoria_mb: float
    capas: int            # capas de velocidad recomendadas para un kit
    kit_max_mb: float     # tamaño recomendado para UN kit (deja sitio para otros packs)
    nota: str
    capas_platos: bool = True   # capas también en platos (son largos y pesan más)


MODELOS = {
    "PSR-S670": Modelo("PSR-S670", 32, 2, 4.0, "Memoria muy limitada: kits compactos, 2 capas y sin capas en platos.", False),
    "PSR-S770": Modelo("PSR-S770", 160, 3, 20.0, "Memoria media: 3 capas de velocidad sin problema."),
    "PSR-S775": Modelo("PSR-S775", 280, 3, 30.0, "Memoria media-alta: 3 capas de velocidad."),
    "PSR-S970": Modelo("PSR-S970", 512, 3, 50.0, "Memoria amplia."),
    "PSR-S975": Modelo("PSR-S975", 768, 3, 60.0, "Memoria amplia."),
}

POR_DEFECTO = "PSR-S670"


def compatibilidad(mb: float) -> list[tuple[str, str, str]]:
    """Para cada modelo: (nombre, estado, texto). estado = OK | AVISO | ERROR."""
    out = []
    for m in MODELOS.values():
        pct = mb / m.memoria_mb * 100
        if mb > m.memoria_mb:
            out.append((m.nombre, "ERROR", f"{mb:.1f} MB no cabe en {m.memoria_mb:.0f} MB"))
        elif mb > m.kit_max_mb:
            out.append((m.nombre, "AVISO", f"{pct:.0f} % de la memoria: deja poco sitio para otros packs"))
        else:
            out.append((m.nombre, "OK", f"{pct:.1f} % de {m.memoria_mb:.0f} MB"))
    return out
