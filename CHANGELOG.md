# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [versionado semántico](https://semver.org/lang/es/).

## [5.1.0] - 2026-11-23

### Estilos del teclado (.sty)
- **Carga un estilo Yamaha** (.sty, .prs, .sst…) en «Escuchar» o «En vivo» y escucha la batería del estilo
  (Rhythm 1 y 2) tocada con tu kit, con el volumen de cada canal de ritmo del estilo.
- **Botones como en la serie PSR-S**: Intro A/B/C, Main A/B/C/D, Break y Ending A/B/C (Intro D y Ending D si el
  estilo los trae). **Auto Fill**: al cambiar de Main suena el Fill del nuevo Main; pulsar el Main que ya suena toca
  su Fill. Los Fill entran en el siguiente pulso; Intro, Ending y cambios sin Fill, en el siguiente compás.
- Tempo del estilo o el tuyo; en «Escuchar» también por el PSR real (MIDI) o con las muestras originales.
- **Aviso de sonidos que faltan**: qué notas usa el estilo que el kit no tiene (pandereta, shaker, congas…) y qué
  parte de los golpes representan.
- **Demo MP3 con el estilo**: Intro, cada Main con su Fill y Ending. En la línea de comandos: `estilo` y `demo --estilo`.
- 5 pruebas automáticas nuevas (34 en total).

### App para el móvil (web app)
- **PPF Tester en iPhone, Android y el navegador** (`docs/app`, publicada en GitHub Pages): abre un `.ppf`, tócalo con
  **pads** (más abajo = más fuerte) o con un teclado MIDI (Android/PC), ritmos de prueba, **estilos .sty** con el
  panel Intro/Main/Fill/Break/Ending, **revisión y compatibilidad** por modelo y **demo WAV** para compartir.
- Usa el mismo núcleo en Python (Pyodide en un worker) que la app de escritorio; el audio se toca con Web Audio,
  con corte de hi-hat y el secuenciador con la misma lógica que el PSR. Solo se renderiza una vez cada capa de
  velocidad real del kit, para que quepa en la memoria del teléfono.
- **Instalable y sin conexión** (manifest + service worker). Los archivos se procesan en el teléfono.
- `python build.py web` copia el núcleo a la web app; una prueba avisa si se queda desactualizado (37 pruebas en total).

## [5.0.0] - 2026-11-22

### Sonido
- **Mezcla de micrófonos**: en kits multi-micrófono (cercano, abajo/afuera, overheads, sala) junta cada golpe y
  deja elegir cuánto «ambiente» lleva. Una carpeta «OH» ya no se confunde con hi-hat abierto.
- **Sala integrada** en las muestras (al importar y en «Mejorar kit»): suena más grande sin gastar efectos del PSR.
- **Capas suaves mejores**: modelo de timbre por velocidad (menos brillo y ataque, más cuerpo relativo, platos que se apagan antes).
- **Nivel como los kits del teclado**: cada pieza a un nivel de referencia para que el kit no salte al cambiar de voz.
- **Fase estéreo**: detecta canales invertidos o desfasados (pérdida de graves en mono) y los corrige.

### Teclado y Expansion Manager
- **Compatibilidad por modelo** (S670 a S975) en «Revisión» y en la línea de comandos (`compat`).
- **Abrir en Expansion Manager** y pasos para instalar en el PSR. El archivo de instalación lo sigue creando
  Expansion Manager porque va cifrado para cada teclado.
- **Asistente paso a paso** para probar en el PSR: conexión, MIDI, audio, prueba completa, calibración e informe.

### Edición
- **Biblioteca de muestras** con búsqueda, etiquetas y favoritos; añade carpetas, kits abiertos o golpes de «Importar WAV».
- **Kit desde cero** con muestras de la biblioteca.
- **Set del teclado**: suma varios packs contra la memoria del modelo y sugiere qué quitar si no caben.
- **Comparar dos versiones** de un kit: qué cambió en cada tecla (capas, nivel, duración, brillo, afinación…) con A/B.

### Voces
- **Voces melódicas multisample**: detecta la nota de cada WAV (por el nombre o por el sonido), reparte el teclado
  y crea la voz usando una plantilla de voz normal hecha en Expansion Manager (comando `voz`).
- **Pads y sonidos sostenidos** con loop sin clics (búsqueda del mejor punto y crossfade).

### App
- **Modo En vivo** con pads grandes, ritmos, entrada MIDI y pantalla completa (F11).
- **Demos en MP3** (o WAV) para compartir: recorrido por cada pieza y ritmos (también `demo` en la línea de comandos).
- **Versión para macOS** (Apple Silicon) y MIDI multiplataforma (python-rtmidi fuera de Windows).
- Más estabilidad: la recolección de memoria de Python se hace solo en el hilo de la interfaz.
- 14 pruebas automáticas nuevas (29 en total).

## [4.0.0] - 2026-11-22

Las 20 mejoras de la hoja de ruta en una sola versión.

### Sonido
- **Variación humana** (round robin aproximado): al tocar, cada golpe varía un poco en afinación, volumen
  y brillo; al importar WAV, cada tecla puede alternar hasta 3 versiones del golpe por tramos de velocidad.
  El PSR no tiene round robin real: esto lo aproxima y ocupa más memoria.
- **Estéreo real** por pieza al importar (Auto / Sí / No), con su coste de memoria en cada modelo.
- **Calibrar la simulación con tu PSR**: toca unas notas por MIDI, las graba y ajusta la simulación
  (curva de tono y respuesta a la velocidad) para que suene como tu teclado.
- **Tocar desde un teclado MIDI** o desde el propio PSR (entrada MIDI) con el kit simulado.
- **Más ritmos** (worship 4/4 con toms, worship 6/8 build, balada 12/8, gospel shuffle, bossa, fill de toms),
  **metrónomo** y **swing**.
- **Grabar un loop** de lo que tocas (simulación o PSR real) y guardarlo en WAV.

### Edición
- **Ajuste fino por pieza** (golpe, cuerpo, brillo) con Antes / Después.
- **Plantillas de mejora**: Worship suave, Worship moderno, Rock potente, Natural, Solo limpieza y las tuyas.
- **Mejorar una carpeta** completa de .ppf para un modelo (también por línea de comandos).
- **Comparar con un kit de referencia**: balance entre piezas, brillo y largo de colas, con sugerencias.
- **Deshacer / rehacer** (Ctrl+Z / Ctrl+Y) en Muestras e Importar WAV.
- **Editor de mapeo**: arrastra una tecla a otra para mover o intercambiar su sonido y edita los rangos de velocidad.
- **Recortes y fades manuales** sobre la forma de onda (clic izquierdo = inicio, derecho = final).

### App
- **Actualización desde la app**: descarga la versión nueva e instala con un clic (versión .exe).
- **Registro de errores** y **reportar un problema** a GitHub con la información técnica (sin datos personales).
- **Idiomas**: español, inglés y portugués (la interfaz; los diagnósticos detallados siguen en español).
- **Tema claro** opcional.
- **Instalador `PPF-Tester-Setup.exe`**: accesos directos, desinstalador y «Abrir con» para archivos .ppf
  (sin quitarle los .ppf a Expansion Manager). Instalación por usuario, sin administrador.
- **Página del programa** en GitHub Pages.
- **Pruebas automáticas** (formato .ppf, audio, importación, mejora, mapeo, idiomas) en cada versión.

## [3.1.0] - 2026-11-22

### Añadido
- **Importar WAV**: elige (o arrastra) una carpeta con golpes de batería y la app arma el `.ppf` sola.
  - Lee WAV PCM 8/16/24/32 bits y float, mono o estéreo, a cualquier frecuencia (se convierte a 44.1 kHz).
  - Detecta cada pieza por las carpetas y el nombre (Kick, Snare, Toms/Floor Tom, Cymbals/Hi Hat…,
    en inglés, español y portugués) o por el sonido, e ignora loops y demos.
  - Agrupa las versiones de cada golpe y las capas de velocidad marcadas en el nombre (soft/hard, pp/ff, v1…).
  - Propone el kit en las teclas General MIDI (bombo 2, caja 2, crash 2, toms afinados en las teclas libres)
    y separa hi-hat cerrado/abierto por su duración.
  - Todo editable: tecla, pieza, versión, capas, afinación y activar/quitar; arrastra filas o archivos al
    piano para mover o asignar piezas (si la tecla está ocupada, se intercambian).
  - Ajusta el kit a la memoria del teclado elegido (S670 a S975) y aplica la mejora por pieza.
- Comando `importar` en la línea de comandos.

## [3.0.0] - 2026-11-22

### Añadido
- Interfaz completamente nueva con Qt (PySide6): barra lateral con indicador animado, tarjetas,
  transiciones de página, tipografía y espaciado profesionales, barra de título oscura.
- Fondo animado estilo worship: luces de escenario, rayos de luz y partículas que laten con el audio.
  Optimizado (≈15 % de un núcleo) y desactivable en Ajustes.
- Pantalla de bienvenida, arrastrar y soltar `.ppf`, archivos recientes, avisos (toasts), atajos
  (Ctrl+O, Ctrl+S, Ctrl+1…5), diálogo de Ajustes y Acerca de con enlaces a angelcm.com y GitHub.
- Piano con brillo al sonar, medidores de nivel, barras de memoria por modelo, logo que pulsa con la música.
- Aviso de nueva versión disponible en GitHub.

### Cambiado
- La interfaz Tkinter se reemplazó por Qt. El motor de audio, el formato `.ppf` y la línea de comandos no cambian.

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
