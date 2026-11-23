# Componentes de terceros

PPF Tester (licencia MIT, © Angel Cm) incluye en sus ejecutables estos componentes, cada uno con su propia licencia:

| Componente | Uso | Licencia |
|---|---|---|
| [Qt for Python (PySide6)](https://www.qt.io/qt-for-python) | Interfaz | LGPL v3 |
| [NumPy](https://numpy.org) | Procesado de audio | BSD |
| [sounddevice](https://python-sounddevice.readthedocs.io) / [PortAudio](https://www.portaudio.com) | Audio de entrada y salida | MIT |
| [lameenc](https://github.com/chrisstaite/lameenc) / [LAME](https://lame.sourceforge.io) | Demos en MP3 | LGPL v3 |
| [python-rtmidi](https://github.com/SpotlightKid/python-rtmidi) / RtMidi | MIDI en macOS | MIT |

Los componentes LGPL se cargan como bibliotecas separadas: puedes reemplazarlos por otra versión
instalando PPF Tester desde el código fuente (`pip install -r requirements.txt`).

Yamaha, PSR y Expansion Manager son marcas de Yamaha Corporation. PPF Tester es un proyecto
independiente y no está afiliado a Yamaha.
