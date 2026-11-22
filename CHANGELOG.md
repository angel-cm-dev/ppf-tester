# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [versionado semántico](https://semver.org/lang/es/).

## [2.0.0] - 2026-11-22

### Añadido
- Nuevo diseño "worship": negro profundo, luces doradas/coral, logo e ícono nuevos.
- Créditos "Desarrollado por Angel Cm" con enlace a angelcm.com (pie, Acerca de e informes).
- Pestaña **Mejorar kit**: procesado por pieza, balance, afinación de toms, corte de hi-hat,
  apertura de filtro y capas de velocidad ligeras, con control de memoria por modelo
  (PSR-S670, S770, S775, S970, S975).
- Pestaña **Escuchar**: simulación del motor del PSR, PSR real por MIDI con monitor y grabación,
  comparación A/B y ritmos de prueba.
- Editor de parámetros por tecla, reemplazo de muestras por WAV, vista de espectro y "Guardar como".
- Comando `mejorar` en la línea de comandos.
- Ejecutable para Windows (`PPF-Tester.exe`) publicado en cada versión.

### Cambiado
- Se eliminó la dependencia de SciPy (filtros con NumPy) para que el ejecutable pese menos.

## [1.0.0] - 2026-11-22

### Añadido
- Lectura y escritura del formato `.ppf` de Yamaha Expansion Manager.
- Análisis de muestras y del kit, correcciones automáticas, exportación a WAV e informe HTML.
- Prueba en el teclado por USB-MIDI con grabación.
