"""Idiomas de la interfaz: español (original), inglés y portugués.

La interfaz se escribe en español; al arrancar se traducen los textos de los
controles con estos diccionarios. Los diagnósticos detallados siguen en español.
"""
from __future__ import annotations

IDIOMAS = {"es": "Español", "en": "English", "pt": "Português"}
ACTUAL = "es"

T = {
    # ------------------------------------------------------------------ general
    "Bienvenido": ("Welcome", "Bem-vindo"),
    "Abre un kit para empezar.": ("Open a kit to get started.", "Abra um kit para começar."),
    "Abrir": ("Open", "Abrir"),
    "Guardar como": ("Save as", "Salvar como"),
    "Informe": ("Report", "Relatório"),
    "WAV": ("WAV", "WAV"),
    "Pack": ("Pack", "Pack"),
    "Voces": ("Voices", "Vozes"),
    "Muestras": ("Samples", "Amostras"),
    "Audio": ("Audio", "Áudio"),
    "Errores": ("Errors", "Erros"),
    "Avisos": ("Warnings", "Avisos"),
    "Notas": ("Notes", "Notas"),
    "Importar WAV": ("Import WAV", "Importar WAV"),
    "Escuchar": ("Listen", "Ouvir"),
    "Mejorar kit": ("Improve kit", "Melhorar kit"),
    "Revisión": ("Review", "Revisão"),
    "Teclado": ("Keyboard", "Teclado"),
    "Desarrollado por": ("Developed by", "Desenvolvido por"),
    "Ajustes": ("Settings", "Ajustes"),
    "Guardar": ("Save", "Salvar"),
    "Ajustes guardados": ("Settings saved", "Ajustes salvos"),
    "Animaciones de fondo (luces de escenario)": ("Background animations (stage lights)", "Animações de fundo (luzes de palco)"),
    "Buscar actualizaciones al iniciar": ("Check for updates at startup", "Procurar atualizações ao iniciar"),
    "Desactiva las animaciones si tu PC es lento o prefieres la app quieta.": (
        "Turn off animations if your PC is slow or you prefer a still app.",
        "Desative as animações se o seu PC for lento ou se preferir o app parado."),
    "Nueva versión disponible": ("New version available", "Nova versão disponível"),
    "Licencia MIT · No afiliado a Yamaha Corporation": ("MIT License · Not affiliated with Yamaha Corporation",
                                                        "Licença MIT · Não afiliado à Yamaha Corporation"),
    "Arrastra aquí tu kit .ppf o una carpeta de WAV": ("Drop your .ppf kit or a WAV folder here", "Arraste aqui seu kit .ppf ou uma pasta de WAV"),
    "Abrir archivo .ppf": ("Open .ppf file", "Abrir arquivo .ppf"),
    "Crear kit desde mis WAV": ("Create kit from my WAVs", "Criar kit com meus WAV"),
    "Recientes": ("Recent", "Recentes"),
    "Suelta para abrir el kit": ("Drop to open the kit", "Solte para abrir o kit"),
    "Suelta la carpeta para crear un kit con tus WAV": ("Drop the folder to create a kit from your WAVs",
                                                        "Solte a pasta para criar um kit com seus WAV"),
    "Suelta el archivo .ppf para abrirlo": ("Drop the .ppf file to open it", "Solte o arquivo .ppf para abri-lo"),
    "Deshecho": ("Undone", "Desfeito"),
    "Rehecho": ("Redone", "Refeito"),
    "No hay nada que deshacer.": ("Nothing to undo.", "Nada para desfazer."),
    "No hay nada que rehacer.": ("Nothing to redo.", "Nada para refazer."),
    "No encuentro ese archivo.": ("File not found.", "Arquivo não encontrado."),
    "Informe abierto en el navegador": ("Report opened in the browser", "Relatório aberto no navegador"),
    "Por seguridad no se sobrescribe el archivo original.": ("For safety, the original file is never overwritten.",
                                                             "Por segurança, o arquivo original não é sobrescrito."),
    "Idioma": ("Language", "Idioma"),
    "Tema": ("Theme", "Tema"),
    "Oscuro": ("Dark", "Escuro"),
    "Claro": ("Light", "Claro"),
    "El idioma y el tema se aplican al reiniciar la app.": ("Language and theme apply after restarting the app.",
                                                            "Idioma e tema são aplicados ao reiniciar o app."),
    "Reiniciar ahora": ("Restart now", "Reiniciar agora"),
    "Reportar un problema": ("Report a problem", "Reportar um problema"),
    "Abrir registros": ("Open logs", "Abrir registros"),
    "Buscar actualizaciones": ("Check for updates", "Procurar atualizações"),
    "Tienes la última versión.": ("You have the latest version.", "Você tem a versão mais recente."),
    "Actualizar a": ("Update to", "Atualizar para"),
    "Sin conexión con GitHub.": ("No connection to GitHub.", "Sem conexão com o GitHub."),
    # ------------------------------------------------------------------ muestras
    "Cada tecla del kit, su forma de onda, espectro, medidas y parámetros.": (
        "Every key in the kit: waveform, spectrum, measurements and parameters.",
        "Cada tecla do kit: forma de onda, espectro, medidas e parâmetros."),
    "Teclas del kit": ("Kit keys", "Teclas do kit"),
    "Tecla": ("Key", "Tecla"),
    "Muestra": ("Sample", "Amostra"),
    "Pico": ("Peak", "Pico"),
    "Estado": ("Status", "Estado"),
    "Parar": ("Stop", "Parar"),
    "Espectro": ("Spectrum", "Espectro"),
    "Forma de onda": ("Waveform", "Forma de onda"),
    "Reemplazar con WAV": ("Replace with WAV", "Substituir por WAV"),
    "Recorte": ("Trim", "Corte"),
    "Aplicar recorte": ("Apply trim", "Aplicar corte"),
    "Clic izquierdo en la onda = inicio · clic derecho = final": ("Left-click the wave = start · right-click = end",
                                                                  "Clique esquerdo na onda = início · clique direito = fim"),
    "Duración": ("Duration", "Duração"),
    "Canales": ("Channels", "Canais"),
    "DC offset": ("DC offset", "DC offset"),
    "Silencio inicial": ("Leading silence", "Silêncio inicial"),
    "Silencio final": ("Trailing silence", "Silêncio final"),
    "Frecuencia": ("Sample rate", "Frequência"),
    "Parámetros de la tecla": ("Key parameters", "Parâmetros da tecla"),
    "Afinación (st)": ("Tuning (st)", "Afinação (st)"),
    "Volumen (dB)": ("Volume (dB)", "Volume (dB)"),
    "Paneo": ("Pan", "Pan"),
    "Filtro (Hz)": ("Filter (Hz)", "Filtro (Hz)"),
    "Grupo de corte": ("Choke group", "Grupo de corte"),
    "Aplicar": ("Apply", "Aplicar"),
    "Diagnóstico": ("Diagnostics", "Diagnóstico"),
    "Capas de velocidad de la tecla": ("Velocity layers of this key", "Camadas de velocidade da tecla"),
    "Aplicar rangos": ("Apply ranges", "Aplicar faixas"),
    "Cada rango debe ir de menor a mayor.": ("Each range must go from low to high.", "Cada faixa deve ir do menor ao maior."),
    "El recorte es demasiado corto.": ("The trim is too short.", "O corte é curto demais."),
    "Arrastra una fila de la tabla hasta otra tecla para mover (o intercambiar) su sonido": (
        "Drag a table row onto another key to move (or swap) its sound",
        "Arraste uma linha da tabela até outra tecla para mover (ou trocar) o som"),
    "Mover teclas solo está disponible en drum kits.": ("Moving keys is only available for drum kits.",
                                                        "Mover teclas só está disponível em drum kits."),
    # ------------------------------------------------------------------ escuchar
    "Escuchar como en el teclado": ("Listen like on the keyboard", "Ouvir como no teclado"),
    "Toca el kit con el ratón o con el teclado del PC. Compara original, simulación y PSR real.": (
        "Play the kit with the mouse or the PC keyboard. Compare original, simulation and the real PSR.",
        "Toque o kit com o mouse ou o teclado do PC. Compare original, simulação e PSR real."),
    "Más abajo en la tecla = más fuerte  ·  letras del teclado del PC sobre cada tecla  ·  Mayús = acento": (
        "Lower on the key = louder  ·  PC keyboard letters on each key  ·  Shift = accent",
        "Mais embaixo na tecla = mais forte  ·  letras do teclado do PC em cada tecla  ·  Shift = acento"),
    "Qué escuchar": ("What to hear", "O que ouvir"),
    "Simulación": ("Simulation", "Simulação"),
    "PSR real": ("Real PSR", "PSR real"),
    "Original": ("Original", "Original"),
    "Aproximación del motor del PSR, sin el teclado.": ("Approximation of the PSR engine, without the keyboard.",
                                                        "Aproximação do motor do PSR, sem o teclado."),
    "Velocidad": ("Velocity", "Velocidade"),
    "Según dónde pulses la tecla": ("Depends on where you click the key", "Conforme onde clicar na tecla"),
    "Filtro de la voz (paso-bajo del pack)": ("Voice filter (pack low-pass)", "Filtro da voz (passa-baixa do pack)"),
    "Reverb": ("Reverb", "Reverb"),
    "Oír el PSR por el PC (monitor)": ("Hear the PSR through the PC (monitor)", "Ouvir o PSR pelo PC (monitor)"),
    "Grabar cada golpe para comparar": ("Record each hit to compare", "Gravar cada batida para comparar"),
    "Ritmo de prueba": ("Test groove", "Ritmo de teste"),
    "Swing": ("Swing", "Swing"),
    "Metrónomo": ("Metronome", "Metrônomo"),
    "Tocar ritmo": ("Play groove", "Tocar ritmo"),
    "Parar ritmo": ("Stop groove", "Parar ritmo"),
    "Variación humana": ("Human variation", "Variação humana"),
    "Cada golpe suena un poco distinto (afinación, volumen y brillo), como un baterista real": (
        "Each hit sounds slightly different (tuning, volume and brightness), like a real drummer",
        "Cada batida soa um pouco diferente (afinação, volume e brilho), como um baterista real"),
    "Grabar loop": ("Record loop", "Gravar loop"),
    "Detener y guardar": ("Stop and save", "Parar e salvar"),
    "Graba lo que tocas (simulación o PSR real) y guárdalo como WAV": (
        "Record what you play (simulation or real PSR) and save it as WAV",
        "Grave o que você toca (simulação ou PSR real) e salve como WAV"),
    "Entrada MIDI": ("MIDI input", "Entrada MIDI"),
    "Tocar desde MIDI": ("Play from MIDI", "Tocar via MIDI"),
    "Toca el kit desde un teclado MIDI o desde el propio PSR (simulación)": (
        "Play the kit from a MIDI keyboard or from the PSR itself (simulation)",
        "Toque o kit de um teclado MIDI ou do próprio PSR (simulação)"),
    "Calibrar con mi PSR": ("Calibrate with my PSR", "Calibrar com meu PSR"),
    "Toca unas notas en tu PSR, las graba y ajusta la simulación para que suene como tu teclado": (
        "Plays a few notes on your PSR, records them and adjusts the simulation to sound like your keyboard",
        "Toca algumas notas no seu PSR, grava e ajusta a simulação para soar como seu teclado"),
    "Usar calibración": ("Use calibration", "Usar calibração"),
    "Comparación A/B — toca una nota": ("A/B comparison — play a note", "Comparação A/B — toque uma nota"),
    "Grabación del PSR": ("PSR recording", "Gravação do PSR"),
    "Grabando… toca el kit o un ritmo": ("Recording… play the kit or a groove", "Gravando… toque o kit ou um ritmo"),
    "La grabación está vacía.": ("The recording is empty.", "A gravação está vazia."),
    "Entrada MIDI desactivada": ("MIDI input off", "Entrada MIDI desativada"),
    "Toca tu teclado MIDI: suena el kit simulado": ("Play your MIDI keyboard: the simulated kit sounds",
                                                    "Toque seu teclado MIDI: o kit simulado soa"),
    "Simulación calibrada con tu PSR": ("Simulation calibrated with your PSR", "Simulação calibrada com seu PSR"),
    "Aún no hay calibración. Pulsa «Calibrar con mi PSR».": ("No calibration yet. Click «Calibrate with my PSR».",
                                                             "Ainda não há calibração. Clique em «Calibrar com meu PSR»."),
    "Elige la salida MIDI del PSR y la entrada de audio en «Teclado».": (
        "Choose the PSR MIDI output and the audio input in «Keyboard».",
        "Escolha a saída MIDI do PSR e a entrada de áudio em «Teclado»."),
    "(sin entradas MIDI)": ("(no MIDI inputs)", "(sem entradas MIDI)"),
    # ------------------------------------------------------------------ mejorar
    "Procesado por pieza, balance, afinación, capas de velocidad y memoria según tu teclado.": (
        "Per-piece processing, balance, tuning, velocity layers and memory for your keyboard.",
        "Processamento por peça, balanço, afinação, camadas de velocidade e memória para seu teclado."),
    "Plantilla": ("Template", "Modelo"),
    "— elegir —": ("— choose —", "— escolher —"),
    "Borrar": ("Delete", "Apagar"),
    "Guarda los ajustes actuales como plantilla": ("Save the current settings as a template", "Salva os ajustes atuais como modelo"),
    "Teclado destino": ("Target keyboard", "Teclado de destino"),
    "Qué mejorar": ("What to improve", "O que melhorar"),
    "Limpieza (DC, clics, silencio final)": ("Cleanup (DC, clicks, trailing silence)", "Limpeza (DC, cliques, silêncio final)"),
    "Procesado por pieza (EQ, ataque, compresión)": ("Per-piece processing (EQ, attack, compression)",
                                                     "Processamento por peça (EQ, ataque, compressão)"),
    "Balance del kit": ("Kit balance", "Balanço do kit"),
    "Afinar toms y bombos repetidos": ("Tune repeated toms and kicks", "Afinar tons e bumbos repetidos"),
    "Hi-hat: el cerrado corta al abierto": ("Hi-hat: closed chokes open", "Chimbal: o fechado corta o aberto"),
    "Abrir el filtro de la voz": ("Open the voice filter", "Abrir o filtro da voz"),
    "Intensidad": ("Intensity", "Intensidade"),
    "Capas de velocidad": ("Velocity layers", "Camadas de velocidade"),
    "Auto (según modelo)": ("Auto (by model)", "Auto (conforme modelo)"),
    "Sin capas": ("No layers", "Sem camadas"),
    "2 capas": ("2 layers", "2 camadas"),
    "3 capas": ("3 layers", "3 camadas"),
    "Mejorar (vista previa)": ("Improve (preview)", "Melhorar (prévia)"),
    "Guardar .ppf mejorado": ("Save improved .ppf", "Salvar .ppf melhorado"),
    "Antes": ("Before", "Antes"),
    "Después": ("After", "Depois"),
    "Mejorar carpeta…": ("Improve folder…", "Melhorar pasta…"),
    "Mejora todos los .ppf de una carpeta para el teclado elegido": ("Improve every .ppf in a folder for the chosen keyboard",
                                                                     "Melhora todos os .ppf de uma pasta para o teclado escolhido"),
    "Ajuste fino de la muestra elegida": ("Fine-tune the selected sample", "Ajuste fino da amostra escolhida"),
    "Golpe (ataque)": ("Punch (attack)", "Ataque"),
    "Cuerpo": ("Body", "Corpo"),
    "Brillo": ("Brightness", "Brilho"),
    "Aplicar a esta muestra": ("Apply to this sample", "Aplicar a esta amostra"),
    "Reiniciar": ("Reset", "Redefinir"),
    "Memoria en la serie S": ("Memory on the S series", "Memória na série S"),
    "Tipo": ("Type", "Tipo"),
    "Teclas": ("Keys", "Teclas"),
    "Cambios": ("Changes", "Mudanças"),
    "Plantilla guardada": ("Template saved", "Modelo salvo"),
    "Solo se pueden borrar tus plantillas (★).": ("Only your templates (★) can be deleted.", "Só é possível apagar seus modelos (★)."),
    "Vista previa lista — aún no se ha guardado nada": ("Preview ready — nothing saved yet", "Prévia pronta — nada foi salvo ainda"),
    # ------------------------------------------------------------------ revisión
    "Revisión del kit": ("Kit review", "Revisão do kit"),
    "Mapa de teclas, velocidades, muestras repetidas y balance.": ("Key map, velocities, repeated samples and balance.",
                                                                   "Mapa de teclas, velocidades, amostras repetidas e balanço."),
    "Muestras OK": ("Samples OK", "Amostras OK"),
    "Kit": ("Kit", "Kit"),
    "Muestras con observaciones": ("Samples with notes", "Amostras com observações"),
    "Comparar con un kit de referencia": ("Compare with a reference kit", "Comparar com um kit de referência"),
    "Elegir kit de referencia…": ("Choose reference kit…", "Escolher kit de referência…"),
    "Comparación lista": ("Comparison ready", "Comparação pronta"),
    # ------------------------------------------------------------------ teclado
    "Prueba en el teclado": ("Keyboard test", "Teste no teclado"),
    "Toca todas las notas en el PSR por USB-MIDI y graba lo que suena.": (
        "Plays every note on the PSR via USB-MIDI and records what it sounds like.",
        "Toca todas as notas no PSR via USB-MIDI e grava o que soa."),
    "Salida MIDI": ("MIDI output", "Saída MIDI"),
    "Canal": ("Channel", "Canal"),
    "Velocidades": ("Velocities", "Velocidades"),
    "Entrada de audio": ("Audio input", "Entrada de áudio"),
    "Grabar la salida del teclado": ("Record the keyboard output", "Gravar a saída do teclado"),
    "Buscar dispositivos": ("Find devices", "Procurar dispositivos"),
    "Iniciar prueba": ("Start test", "Iniciar teste"),
    "Nivel de entrada": ("Input level", "Nível de entrada"),
    "Resultado": ("Result", "Resultado"),
    "Vel": ("Vel", "Vel"),
    "Retardo": ("Latency", "Latência"),
    "Prueba en el teclado terminada": ("Keyboard test finished", "Teste no teclado concluído"),
    "Elige la salida MIDI del PSR.": ("Choose the PSR MIDI output.", "Escolha a saída MIDI do PSR."),
    "Revisa las velocidades (ej.: 40,80,127).": ("Check the velocities (e.g. 40,80,127).", "Verifique as velocidades (ex.: 40,80,127)."),
    # ------------------------------------------------------------------ importar
    "Elige una carpeta con tus golpes de batería y la app arma tu kit .ppf. Todo es editable.": (
        "Choose a folder with your drum hits and the app builds your .ppf kit. Everything is editable.",
        "Escolha uma pasta com suas batidas de bateria e o app monta seu kit .ppf. Tudo é editável."),
    "Elegir carpeta de WAV": ("Choose WAV folder", "Escolher pasta de WAV"),
    "Arrastra aquí una carpeta con WAV o pulsa el botón.": ("Drop a WAV folder here or click the button.",
                                                             "Arraste aqui uma pasta com WAV ou clique no botão."),
    "Nombre": ("Name", "Nome"),
    "Crear .ppf": ("Create .ppf", "Criar .ppf"),
    "Mejorar cada pieza": ("Improve each piece", "Melhorar cada peça"),
    "Platos en estéreo": ("Stereo cymbals", "Pratos em estéreo"),
    "Dinámica natural entre capas": ("Natural dynamics between layers", "Dinâmica natural entre camadas"),
    "Completar teclas GM": ("Fill GM keys", "Completar teclas GM"),
    "Volver a armar automático": ("Rebuild automatically", "Remontar automaticamente"),
    "Clic en una tecla para escucharla · arrastra una fila (columna Tecla) o un archivo hasta una tecla para moverla o asignarla": (
        "Click a key to hear it · drag a row or a file onto a key to move or assign it",
        "Clique numa tecla para ouvi-la · arraste uma linha ou um arquivo até uma tecla para movê-la ou atribuí-la"),
    "Tu kit": ("Your kit", "Seu kit"),
    "Quitar": ("Remove", "Remover"),
    "Usar": ("Use", "Usar"),
    "Pieza": ("Piece", "Peça"),
    "Versión": ("Version", "Versão"),
    "Capas": ("Layers", "Camadas"),
    "Variar": ("Vary", "Variar"),
    "Estéreo": ("Stereo", "Estéreo"),
    "Afin.": ("Tune", "Afin."),
    "Archivos encontrados": ("Files found", "Arquivos encontrados"),
    "Añadir a tecla libre": ("Add to free key", "Adicionar à tecla livre"),
    "Memoria del kit": ("Kit memory", "Memória do kit"),
    "Auto": ("Auto", "Auto"),
    "Sí": ("Yes", "Sim"),
    "No": ("No", "Não"),
    "Arrastra hasta una tecla del piano para mover esta pieza": ("Drag onto a piano key to move this piece",
                                                                 "Arraste até uma tecla do piano para mover esta peça"),
    "Versión del golpe dentro del grupo": ("Hit version within the group", "Versão da batida no grupo"),
    "Capas de velocidad: golpes suaves y fuertes distintos": ("Velocity layers: different soft and hard hits",
                                                              "Camadas de velocidade: batidas suaves e fortes diferentes"),
    "Estéreo real (solo si el WAV es estéreo). Ocupa el doble de memoria.": (
        "True stereo (only if the WAV is stereo). Uses twice the memory.",
        "Estéreo real (só se o WAV for estéreo). Ocupa o dobro de memória."),
    "No encontré golpes WAV en esa carpeta.": ("No WAV drum hits found in that folder.", "Não encontrei batidas WAV nessa pasta."),
    "Selecciona un archivo o grupo en la lista.": ("Select a file or group in the list.", "Selecione um arquivo ou grupo na lista."),
    "No quedan teclas libres.": ("No free keys left.", "Não há teclas livres."),
    # piezas
    "Bombo": ("Kick", "Bumbo"), "Caja": ("Snare", "Caixa"), "Aro / Side stick": ("Rim / Side stick", "Aro / Side stick"),
    "Palmas": ("Clap", "Palmas"), "Tom": ("Tom", "Tom"), "Hi-hat cerrado": ("Closed hi-hat", "Chimbal fechado"),
    "Hi-hat pedal": ("Pedal hi-hat", "Chimbal de pedal"), "Hi-hat abierto": ("Open hi-hat", "Chimbal aberto"),
    "Crash": ("Crash", "Crash"), "Ride": ("Ride", "Condução"), "Campana del ride": ("Ride bell", "Cúpula da condução"),
    "Splash": ("Splash", "Splash"), "China": ("China", "China"), "Pandereta": ("Tambourine", "Pandeiro"),
    "Cencerro": ("Cowbell", "Cowbell"), "Shaker": ("Shaker", "Shaker"), "Percusión": ("Percussion", "Percussão"),

    # ------------------------------------------------------------------ versión 5
    "Biblioteca": ("Library", "Biblioteca"),
    "Voces y pads": ("Voices and pads", "Vozes e pads"),
    "En vivo": ("Live", "Ao vivo"),
    "Set del teclado": ("Keyboard set", "Set do teclado"),
    "Biblioteca de muestras": ("Sample library", "Biblioteca de amostras"),
    "Tus golpes favoritos guardados para reutilizarlos. Busca, etiqueta y arma kits nuevos desde aquí.": (
        "Your favourite hits saved for reuse. Search, tag and build new kits from here.",
        "Seus toques favoritos salvos para reutilizar. Busque, etiquete e monte kits novos daqui."),
    "Buscar: caja seca, worship, room…": ("Search: dry snare, worship, room…", "Buscar: caixa seca, worship, room…"),
    "Todas las piezas": ("All pieces", "Todas as peças"),
    "Todas las etiquetas": ("All tags", "Todas as etiquetas"),
    "Solo favoritos": ("Favourites only", "Só favoritos"),
    "Añadir carpeta": ("Add folder", "Adicionar pasta"),
    "Añadir el kit abierto": ("Add the open kit", "Adicionar o kit aberto"),
    "Con lo seleccionado": ("With the selection", "Com a seleção"),
    "Favorito ★": ("Favourite ★", "Favorito ★"),
    "Etiquetas…": ("Tags…", "Etiquetas…"),
    "Etiquetas": ("Tags", "Etiquetas"),
    "Renombrar…": ("Rename…", "Renomear…"),
    "Kit nuevo con estas muestras": ("New kit with these samples", "Kit novo com estas amostras"),
    "Añadir al kit de «Importar WAV»": ("Add to the «Import WAV» kit", "Adicionar ao kit de «Importar WAV»"),
    "Quitar de la biblioteca": ("Remove from library", "Remover da biblioteca"),
    "Nombre": ("Name", "Nome"),
    "Pieza": ("Piece", "Peça"),
    "Origen": ("Source", "Origem"),
    "Voces melódicas (piano, cuerdas, pads) desde tus WAV: detecta la nota y hace loops sin clics.": (
        "Melodic voices (piano, strings, pads) from your WAVs: detects each note and makes click-free loops.",
        "Vozes melódicas (piano, cordas, pads) dos seus WAV: detecta a nota e faz loops sem cliques."),
    "Plantilla de voz": ("Voice template", "Modelo de voz"),
    "Elegir plantilla…": ("Choose template…", "Escolher modelo…"),
    "¿Cómo la creo?": ("How do I make one?", "Como criar?"),
    "Multisample (piano, guitarra…)": ("Multisample (piano, guitar…)", "Multisample (piano, violão…)"),
    "Sostenido con loop (cuerdas, órgano)": ("Sustained with loop (strings, organ)", "Sustentado com loop (cordas, órgão)"),
    "Pad / ambiente (un WAV)": ("Pad / ambience (one WAV)", "Pad / ambiente (um WAV)"),
    "Elegir WAV…": ("Choose WAV…", "Escolher WAV…"),
    "Estéreo": ("Stereo", "Estéreo"),
    "Ataque": ("Attack", "Ataque"),
    "Crear .ppf": ("Create .ppf", "Criar .ppf"),
    "Usar": ("Use", "Usar"),
    "Archivo": ("File", "Arquivo"),
    "Nota raíz": ("Root note", "Nota raiz"),
    "Afinación": ("Tuning", "Afinação"),
    "Detectada por": ("Detected by", "Detectada por"),
    "Loop": ("Loop", "Loop"),
    "Cada color es una zona del teclado: la muestra se estira a las teclas vecinas. Clic en una tecla para escucharla.": (
        "Each colour is a keyboard zone: the sample is stretched to neighbouring keys. Click a key to hear it.",
        "Cada cor é uma zona do teclado: a amostra se estende às teclas vizinhas. Clique numa tecla para ouvir."),
    "Junta los packs que quieres instalar y mira si caben en la memoria de tu PSR. Compara dos versiones de un kit.": (
        "Gather the packs you want installed and check they fit your PSR memory. Compare two versions of a kit.",
        "Junte os packs que quer instalar e veja se cabem na memória do seu PSR. Compare duas versões de um kit."),
    "Packs del set": ("Packs in the set", "Packs do set"),
    "Añadir .ppf…": ("Add .ppf…", "Adicionar .ppf…"),
    "Añadir el abierto": ("Add the open one", "Adicionar o aberto"),
    "Quitar": ("Remove", "Remover"),
    "Tipo": ("Type", "Tipo"),
    "% memoria": ("% memory", "% memória"),
    "Comparar dos versiones de un kit": ("Compare two versions of a kit", "Comparar duas versões de um kit"),
    "A: elegir…": ("A: choose…", "A: escolher…"),
    "B: elegir…": ("B: choose…", "B: escolher…"),
    "Escuchar A": ("Play A", "Ouvir A"),
    "Escuchar B": ("Play B", "Ouvir B"),
    "Añade los .ppf que quieres tener instalados a la vez.": ("Add the .ppf files you want installed at the same time.",
                                                             "Adicione os .ppf que quer ter instalados ao mesmo tempo."),
    "Pads grandes para tocar el kit en el ensayo: ratón, teclado del PC o MIDI. F11 = pantalla completa.": (
        "Big pads to play the kit at rehearsal: mouse, PC keyboard or MIDI. F11 = full screen.",
        "Pads grandes para tocar o kit no ensaio: mouse, teclado do PC ou MIDI. F11 = tela cheia."),
    "Ritmo": ("Groove", "Ritmo"),
    "Volumen": ("Volume", "Volume"),
    "Entrada MIDI": ("MIDI input", "Entrada MIDI"),
    "Tocar desde MIDI": ("Play from MIDI", "Tocar via MIDI"),
    "Abajo en el pad = más fuerte · Mayús = acento": ("Lower on the pad = louder · Shift = accent",
                                                      "Mais abaixo no pad = mais forte · Shift = acento"),
    "Pantalla completa": ("Full screen", "Tela cheia"),
    "Demo MP3": ("MP3 demo", "Demo MP3"),
    "Compatibilidad por modelo": ("Compatibility by model", "Compatibilidade por modelo"),
    "Expansion Manager": ("Expansion Manager", "Expansion Manager"),
    "Instalar en el PSR": ("Install on the PSR", "Instalar no PSR"),
    "Asistente paso a paso": ("Step-by-step assistant", "Assistente passo a passo"),
    "Nivel como el teclado": ("Keyboard-like level", "Nível como o teclado"),
    "Nivel como los kits del teclado": ("Level like the keyboard's kits", "Nível como os kits do teclado"),
    "Corregir fase de muestras estéreo": ("Fix stereo sample phase", "Corrigir fase de amostras estéreo"),
    "Sala integrada": ("Built-in room", "Sala integrada"),
    "Kit vacío": ("Empty kit", "Kit vazio"),
    "A la biblioteca": ("To library", "Para a biblioteca"),
    "Qué incluir": ("What to include", "O que incluir"),
    "Recorrido: cada pieza suave y fuerte": ("Walkthrough: each piece soft and loud", "Percurso: cada peça suave e forte"),
    "Compases por ritmo": ("Bars per groove", "Compassos por ritmo"),
    "Crear demo": ("Create demo", "Criar demo"),
    "Cancelar": ("Cancel", "Cancelar"),
    "MP3 (para WhatsApp y redes)": ("MP3 (for WhatsApp and social media)", "MP3 (para WhatsApp e redes)"),
    "WAV (calidad completa)": ("WAV (full quality)", "WAV (qualidade total)"),
    "Atrás": ("Back", "Voltar"),
    "Siguiente": ("Next", "Próximo"),
    "Cerrar": ("Close", "Fechar"),
    "Salida MIDI (el PSR)": ("MIDI output (the PSR)", "Saída MIDI (o PSR)"),
    "Entrada de audio": ("Audio input", "Entrada de áudio"),
    "Canal": ("Channel", "Canal"),
    "Tocar nota de prueba": ("Play test note", "Tocar nota de teste"),
    "Sí, sonó": ("Yes, it played", "Sim, tocou"),
    "No sonó": ("No sound", "Não tocou"),
    "Tocar notas de prueba": ("Play test notes", "Tocar notas de teste"),
    "Iniciar la prueba": ("Start the test", "Iniciar o teste"),
    "Calibrar también la simulación con mi PSR": ("Also calibrate the simulation with my PSR",
                                                 "Calibrar também a simulação com meu PSR"),
    "Guardar informe HTML": ("Save HTML report", "Salvar relatório HTML"),
    # ------------------------------------------------------------------ estilos (.sty)
    "Estilo del teclado (.sty)": ("Keyboard style (.sty)", "Estilo do teclado (.sty)"),
    "Carga un estilo de tu PSR para oír su batería con este kit.": ("Load a style from your PSR to hear its drums with this kit.", "Carregue um estilo do seu PSR para ouvir a bateria dele com este kit."),
    "Cargar estilo…": ("Load style…", "Carregar estilo…"),
    "Archivos .sty de tu PSR (USB o PC). Solo suena la batería del estilo, con tu kit.": ("Style files (.sty) from your PSR (USB or PC). Only the style's drums play, with your kit.", "Arquivos .sty do seu PSR (USB ou PC). Só a bateria do estilo toca, com o seu kit."),
    "Como en el PSR: al pulsar un Main suena su Fill antes de cambiar.\nPulsar el Main que ya suena toca su Fill.": ("Like on the PSR: pressing a Main plays its Fill before switching.\nPressing the Main that is playing plays its Fill.", "Como no PSR: ao apertar um Main toca a virada dele antes de trocar.\nApertar o Main que está tocando toca a virada."),
    "Tempo": ("Tempo", "Andamento"),
    "Tempo original del estilo": ("Original style tempo", "Andamento original do estilo"),
    "START/STOP del estilo": ("Style START/STOP", "START/STOP do estilo"),
    "Elegir estilo": ("Choose style", "Escolher estilo"),
    "Estilo del teclado (carga un .sty en Escuchar o En vivo)": ("Keyboard style (load a .sty in Listen or Live)", "Estilo do teclado (carregue um .sty em Ouvir ou Ao vivo)"),
    "Elige al menos el recorrido, el estilo o un ritmo.": ("Choose at least the walkthrough, the style or a rhythm.", "Escolha pelo menos o percurso, o estilo ou um ritmo."),
}


def set_idioma(code: str):
    global ACTUAL
    ACTUAL = code if code in IDIOMAS else "es"


def tr(texto: str) -> str:
    """Traduce un texto de la interfaz (respeta espacios iniciales y mayúsculas de los títulos)."""
    if ACTUAL == "es" or not texto:
        return texto
    idx = 0 if ACTUAL == "en" else 1
    s = texto.strip()
    pre = texto[: len(texto) - len(texto.lstrip())]
    if s in T:
        return pre + T[s][idx]
    for k, v in T.items():                      # títulos en MAYÚSCULAS (caption)
        if s == k.upper():
            return pre + v[idx].upper()
    return texto


def traducir_arbol(widget):
    """Traduce los textos de un widget y de todos sus hijos."""
    if ACTUAL == "es":
        return
    from PySide6.QtWidgets import (QAbstractButton, QComboBox, QLabel, QLineEdit, QTableWidget, QTreeWidget, QWidget)
    for w in [widget] + widget.findChildren(QWidget):
        try:
            if w.property("_tr_done"):
                continue
            if isinstance(w, (QLabel, QAbstractButton)) and w.text() and "<" not in w.text():
                w.setText(tr(w.text()))
            if w.toolTip():
                w.setToolTip(tr(w.toolTip()))
            if isinstance(w, QLineEdit) and w.placeholderText():
                w.setPlaceholderText(tr(w.placeholderText()))
            if isinstance(w, QComboBox):
                for i in range(w.count()):
                    w.setItemText(i, tr(w.itemText(i)))
            if isinstance(w, QTableWidget):
                for i in range(w.columnCount()):
                    it = w.horizontalHeaderItem(i)
                    if it is not None:
                        it.setText(tr(it.text()))
            w.setProperty("_tr_done", True)
        except RuntimeError:
            pass
