<p align="center">
  <img src="docs/logo.png" width="96" alt="PPF Tester">
</p>

<h1 align="center">PPF Tester</h1>

<p align="center">
  <b>Sample Lab para Yamaha PSR-S670 · S770 · S775 · S970 · S975</b><br>
  Analiza, escucha, compara y mejora tus packs <code>.ppf</code> de Yamaha Expansion Manager.<br>
  Desarrollado por <a href="https://angelcm.com"><b>Angel Cm</b></a> · <a href="https://angelcm.com">angelcm.com</a>
</p>

<p align="center">
  <a href="https://github.com/angel-cm-dev/ppf-tester/releases/latest"><img alt="Descargar" src="https://img.shields.io/github/v/release/angel-cm-dev/ppf-tester?label=descargar&color=f4b860&style=for-the-badge"></a>
  <a href="LICENSE"><img alt="Licencia MIT" src="https://img.shields.io/badge/licencia-MIT-ec6f7f?style=for-the-badge"></a>
  <img alt="Windows" src="https://img.shields.io/badge/Windows-10%20%7C%2011-8b6cff?style=for-the-badge">
  <img alt="macOS" src="https://img.shields.io/badge/macOS-Apple%20Silicon-5aa9ff?style=for-the-badge">
</p>

<p align="center">
  <img src="docs/samples.jpg" width="860" alt="Muestras">
</p>

## Novedades de la versión 5

- **Sonido**: mezcla de micrófonos (cercano / overheads / sala) en kits multi-micrófono, **sala integrada**,
  capas suaves con un modelo de timbre por velocidad, **nivel como los kits del teclado** y detección y
  corrección de **fase** en muestras estéreo.
- **Compatibilidad por modelo** (S670 a S975) y botón para **abrir el kit en Expansion Manager**, con los pasos
  para instalarlo en el PSR.
- **Biblioteca de muestras** (búsqueda, etiquetas, favoritos) y **kits desde cero** con tus golpes guardados.
- **Set del teclado**: varios packs a la vez contra la memoria de tu PSR, y **comparar dos versiones** de un kit
  (qué cambió en cada tecla, con A/B).
- **Voces y pads**: voces melódicas multisample (detecta la nota de cada WAV) y **pads con loop sin clics**.
- **Modo En vivo** con pads grandes, **demos en MP3** para WhatsApp y **asistente paso a paso** para probar en el PSR.
- **Versión para Mac** (Apple Silicon).

## Novedades de la versión 4

- **Importar WAV** con variación humana (round robin aproximado) y estéreo real por pieza.
- **Calibrar con tu PSR**, tocar desde un **teclado MIDI**, más ritmos con **metrónomo y swing**, y **grabar loops**.
- **Ajuste fino por pieza**, **plantillas**, **mejorar carpetas enteras** y **comparar con un kit de referencia**.
- **Deshacer/rehacer**, **editor de mapeo** (arrastrar teclas, rangos de velocidad) y **recortes/fades**.
- **Instalador**, **actualización desde la app**, **idiomas** (español, inglés, portugués), **tema claro**,
  registro de errores y pruebas automáticas.
- Página del programa: https://angel-cm-dev.github.io/ppf-tester/

## Novedades de la versión 3

- Interfaz nueva en **Qt**: barra lateral, tarjetas, transiciones suaves y tipografía cuidada.
- **Fondo animado estilo worship**: luces de escenario que se mueven y respiran, rayos de luz y partículas
  que **laten con la música** cuando tocas el kit (se puede desactivar en Ajustes).
- Pantalla de bienvenida, **arrastrar y soltar** archivos `.ppf`, archivos recientes y avisos discretos.
- Piano que brilla al sonar, medidores de nivel y barras de memoria por modelo.
- Aviso automático cuando hay una versión nueva en GitHub.

<p align="center">
  <img src="docs/empty.jpg" width="860" alt="Bienvenida">
</p>

## Qué hace

| | |
|---|---|
| **Importar WAV** | Arrastra una carpeta con tus golpes de batería y la app arma el `.ppf`: detecta bombo, caja, toms, hi-hat y platos, junta versiones y capas, y lo ajusta a la memoria de tu teclado. Puedes mover piezas al piano arrastrándolas. |
| **Muestras** | Piano con el estado de cada tecla, forma de onda, espectro, medidas (pico, RMS, DC, silencios) y editor por tecla (afinación, volumen, paneo, filtro, grupo de corte). Reemplaza una muestra por un WAV. |
| **Escuchar** | Toca el kit con el ratón o el teclado del PC: *simulación del PSR* (curva de velocidad, filtro, paneo, reverb), *PSR real por MIDI* (sonido exacto, con monitor y grabación) o la *muestra original*. Comparación A/B y ritmos de prueba (balada, worship 6/8, pop, rock, toms, dinámica). |
| **Mejorar kit** | Elige el teclado destino y mejora todo: limpieza, procesado por pieza (bombo, caja, toms, hi-hat, ride, crash), balance, afinación de toms, corte de hi-hat, filtro y capas de velocidad ligeras. Controla la memoria de cada modelo. |
| **Revisión** | Huecos de velocidad, muestras repetidas, estéreo falso, fase, hi-hat sin corte, balance y compatibilidad con cada modelo. Abre el kit en Expansion Manager. |
| **Biblioteca** | Guarda tus mejores golpes, búscalos por nombre, pieza o etiqueta y arma kits nuevos desde cero. |
| **Voces y pads** | Pianos, cuerdas o pads desde tus WAV: detecta la nota de cada muestra, reparte el teclado y crea loops sin clics. |
| **En vivo** | Pads grandes para el ensayo (ratón, teclado del PC o MIDI), ritmos y pantalla completa. Exporta una demo en MP3. |
| **Set del teclado** | Comprueba si todos tus packs caben juntos en la memoria del PSR y compara dos versiones de un kit. |
| **Prueba en el teclado** | Toca todas las notas en el PSR por USB-MIDI, graba la salida y detecta notas mudas, retardos y dinámica incorrecta. |

<p align="center">
  <img src="docs/listen.jpg" width="425" alt="Escuchar">
  <img src="docs/improve.jpg" width="425" alt="Mejorar kit">
</p>
<p align="center">
  <img src="docs/review.jpg" width="425" alt="Revisión">
  <img src="docs/about.jpg" width="300" alt="Acerca de">
</p>

## Memoria de expansión por modelo

| Modelo | Memoria | Recomendado por kit | Capas de velocidad (auto) |
|---|---|---|---|
| PSR-S670 | ≈ 32 MB | ≤ 4 MB | 2 (sin capas en platos) |
| PSR-S770 | 160 MB | ≤ 20 MB | 3 |
| PSR-S775 | 280 MB | ≤ 30 MB | 3 |
| PSR-S970 | 512 MB | ≤ 50 MB | 3 |
| PSR-S975 | 768 MB | ≤ 60 MB | 3 |

## Descarga (recomendado)

1. Ve a **[Releases](https://github.com/angel-cm-dev/ppf-tester/releases/latest)** y descarga **`PPF-Tester-Setup-vX.Y.Z.exe`** (instalador)
   o **`PPF-Tester.exe`** (portable, sin instalar).
2. Ábrelo. No necesitas instalar Python ni nada más (≈ 55 MB, Windows 10/11). La app avisa e instala sola las versiones nuevas.

> Windows SmartScreen puede avisar la primera vez porque el ejecutable no está firmado:
> pulsa **“Más información” → “Ejecutar de todas formas”**.

**Mac (Apple Silicon, M1 o posterior):** descarga **`PPF-Tester-vX.Y.Z-macos.zip`**, descomprímelo y mueve
**PPF Tester** a Aplicaciones. Como la app no está firmada por Apple, la primera vez haz **clic derecho → Abrir**
(o en Ajustes del Sistema → Privacidad y seguridad → «Abrir igualmente»).

## Ejecutar desde el código

1. Instala [Python 3.10 o superior](https://www.python.org/downloads/) marcando **“Add Python to PATH”**.
2. Descarga este repositorio y haz doble clic en **`Instalar.bat`** (instala `numpy`, `sounddevice`, `PySide6` y `lameenc`).
   En Mac/Linux: `pip install -r requirements.txt` (incluye `python-rtmidi` para el MIDI).
3. Abre el programa con **`PPF Tester.bat`**.

O desde la consola:

```powershell
pip install -r requirements.txt
python ppf_tester/qt_main.py
```

## Línea de comandos

```powershell
python ppf_tester/ppf_tester.py analizar MI_KIT.ppf --abrir
python ppf_tester/ppf_tester.py importar "C:\Mis WAV\Real Drums" --modelo S670
python ppf_tester/ppf_tester.py mejorar  MI_KIT.ppf --modelo S670
python ppf_tester/ppf_tester.py mejorar-carpeta "C:\Mis kits" --modelo S670
python ppf_tester/ppf_tester.py importar "C:\Mis WAV\Kit multi-mic" --ambiente 30 --sala 20
python ppf_tester/ppf_tester.py compat   MI_KIT.ppf
python ppf_tester/ppf_tester.py demo     MI_KIT.ppf --ritmos "Worship 6/8,Pop 4/4"
python ppf_tester/ppf_tester.py voz      "C:\Mis WAV\Piano" --plantilla VOZ_NORMAL.ppf
python ppf_tester/ppf_tester.py voz      PAD.wav --pad --ataque 0.8 --plantilla VOZ_NORMAL.ppf
python -m unittest discover -s tests          # pruebas automáticas
python ppf_tester/ppf_tester.py corregir MI_KIT.ppf --agrupar-hihat
python ppf_tester/ppf_tester.py extraer  MI_KIT.ppf
python ppf_tester/ppf_tester.py puertos
python ppf_tester/ppf_tester.py teclado  MI_KIT.ppf --grabar --entrada 1
```

## Voces melódicas y pads

Para crear voces (no baterías) la app necesita **una vez** una voz normal hecha en Yamaha Expansion Manager:
crea un pack, añade una voz normal con cualquier WAV y guárdalo como `.ppf`. En **Voces y pads → Elegir plantilla…**
elígelo: la app usa solo su estructura y pone tus muestras. Nombra los WAV con su nota (`Piano_C3.wav`, `Pad A#2.wav`)
o deja que la app la detecte por el sonido.

## Probar en el PSR

Lo más fácil: **Teclado → Asistente paso a paso**. A mano:

1. Conecta el PSR al PC por **USB TO HOST** y la salida de auriculares del PSR a tu interfaz de audio.
2. Instala el pack en el teclado y elige la voz en **RIGHT 1**.
3. En **Prueba en el teclado**, elige la salida MIDI del PSR y la entrada de audio.
4. En **Escuchar**, elige **PSR real por MIDI** y toca, o pulsa **Tocar ritmo**.

> Antes de instalar un pack mejorado en el teclado, ábrelo en **Yamaha Expansion Manager** y escúchalo.
> Recuerda que instalar un archivo de instalación reemplaza toda la memoria de expansión del teclado.

## Publicar una versión nueva (mantenedor)

1. Cambia el número en `ppf_tester/version.py` y anota los cambios en `CHANGELOG.md`.
2. Sube los cambios y crea la etiqueta:

```powershell
git commit -am "Versión 2.1.0"
git tag v2.1.0
git push origin main --tags
```

GitHub Actions compila `PPF-Tester.exe`, el instalador y la app de Mac, y los publica en **Releases** automáticamente.
Para compilarlo en tu PC: `Compilar exe.bat` (resultado en `dist\`).

## Formato .ppf (referencia técnica)

Contenedor `XPFH` con bloques `TAG + longitud (big-endian)` alineados a 4 bytes. Cada recurso es un `BLOB`
con `EUID`, `ETIT`, `EEXT` (`uvf` = voz en XML, `APCp` = onda) y `FBIN`. Las ondas son AIFF tipo `YTWV`
(PCM 16 bits) y su `EUID` es el SHA-1 del contenido; el programa lo recalcula al modificar una muestra.

## Hoja de ruta

Mira la [hoja de ruta](ROADMAP.md) y el [historial de cambios](CHANGELOG.md).

## Licencia

[MIT](LICENSE) © 2026 [Angel Cm](https://angelcm.com). Puedes usarlo, modificarlo y compartirlo manteniendo el aviso de autoría.
Componentes de terceros: [THIRD_PARTY.md](THIRD_PARTY.md).

---

<p align="center">
  Hecho con ♥ para músicos de alabanza · <a href="https://angelcm.com"><b>Angel Cm</b></a><br>
  <sub>No afiliado a Yamaha Corporation. “Yamaha”, “PSR” y “Expansion Manager” son marcas de sus respectivos dueños.</sub>
</p>
