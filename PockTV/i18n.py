"""Textos de la interfaz en Español e Inglés. T("clave", args...) devuelve el texto en el idioma activo."""

LANG = ["es"]

S = {
    "es": {
        "tile_TV": "TV en vivo", "tile_PELIS": "Películas", "tile_SERIES": "Series", "tile_FAV": "Favoritos", "tile_ALL": "Búsqueda maestra",
        "kind_TV": "TV", "kind_PELIS": "Película", "kind_SERIES": "Serie",
        "unit_TV": "canales", "unit_PELIS": "películas", "unit_SERIES": "series", "unit_FAV": "favoritos",
        "icon_search": "Búsqueda maestra", "icon_update": "Actualizar Listas", "icon_lists": "Cambiar de Lista", "icon_settings": "Ajustes",
        "footer_list": "Lista: %s  ·  %d entradas", "footer_keys": "A  Entrar      B  Salir",
        "filter_on": "Idioma del contenido: %s",
        "no_list": "Falta lista.m3u en App/PockTV (o lista.url)",
        "list_hint": "A Reproducir   X Favorito   Y Buscar   B %s", "list_back": "Atrás", "list_clear": "Quitar búsqueda",
        "no_results": 'Sin resultados para "%s"', "no_results_hint": "B: quitar la búsqueda    Y: buscar otra cosa",
        "no_favs": "Aún no tienes favoritos", "no_favs_1": "En cualquier lista, resalta un canal, categoría o serie y presiona X",
        "no_favs_2": "para marcarlo con una estrella",
        "no_entries": "No hay entradas en esta categoría", "no_entries_hint": "Revisa tu lista o el idioma del contenido en Ajustes",
        "search_in": "Buscar en %s", "search_groups": "Buscar en categorías", "search_shows": "Buscar series", "pause_aspect": "Pantalla", "pause_fav": "Favorito", "live_txt": "EN VIVO", "pause_txt": "PAUSA", "play_txt": "REPRODUCIENDO", "pause_audio": "Audio", "pause_subs": "Subtítulos", "pause_subs_s": "Subs", "pause_eps": "Episodios", "pause_next": "Siguiente", "pause_restart": "Reiniciar", "exit_q": "¿Quieres salir?", "exit_yes": "Sí", "exit_no": "No", "fav_loose": "Canales sueltos", "fav_loose_hint": "Marca o quita cada canal dentro de su lista", "fav_in_group": "Quítalo desde la categoría o serie favorita", "fav_via_group": "Está en favoritos por su categoría o serie: quítala desde su lista", "no_group": "Sin categoría", "preview_a": "Presiona « A »", "preview_see": "para ver", "pv_loading": "Cargando…", "pv_fail": "No se pudo", "pv_fail2": "mostrar la previa", "pv_nofmpeg": "Falta ffmpeg para", "pv_again": "« A » otra vez: pantalla completa", "preview_full": "para pantalla completa", "split_hint": "◀ ▶ columna   L/R letra   A Reproducir   X Favorito   Y Buscar   B Atrás", "type_name": "Escribe el nombre…",
        "kb_space": "Espacio", "kb_del": "Borrar", "kb_go": "Buscar", "kb_cancel": "Cancelar",
        "kb_hint": "A Escribir   B Borrar   X Espacio   Start / Y Buscar", "del_ask": "¿Quieres borrar?", "quit_ask": "¿Quieres salir?", "del_main": "La lista principal no se puede borrar aquí", "del_done": "Lista borrada: %s", "del_fail": "No pude borrar la lista", "lists_hint": "A Elegir   X Borrar   B Atrás",
        "opening": "Abriendo…", "play_hint": "Arriba/Abajo: canal   A: video   Izq/Der: -/+10 s   B: volver",
        "settings": "AJUSTES", "cat_lang": "Idioma de Interfaz", "cat_clock": "Reloj y Fecha", "cat_video": "Video",
        "cat_look": "Apariencia", "cat_sound": "Sonido", "snd_off": "Sin sonido", "snd_suave": "Suave", "snd_cristal": "Cristal", "snd_madera": "Madera", "snd_burbuja": "Burbuja", "snd_marimba": "Marimba", "look_cards": "Tarjetas", "look_icons": "Íconos de Interfaz",
        "look_clock": "Reloj / Fecha / Wi-fi", "look_logo": "Logo", "look_fonts": "Letras de Secciones", "sf_def": "Predeterminada · Comic Sans MS", "fx_default": "Predeterminado",
        "fx_A": "A · Zoom con sombra", "fx_B": "B · Brillo que barre", "fx_C": "C · Atenuar las demás", "fx_D": "D · Luz que recorre el borde", "fx_E": "E · Respirar con halo",
        "logo_1": "Flip V2", "logo_2": "Mini Flip", "logo_3": "Mini Plus", "lg_icon": "Icono", "logo_per": "Personalizar", "lg_text": "Texto", "lg_font": "Estilo de letra", "lg_size": "Tamaño",
        "lg_f_A": "Clásica", "lg_f_B": "Cursiva", "lg_f_C": "Elegante", "lg_f_D": "Máquina", "lg_f_E": "Moderna",
        "lg_kb": "Nombre de la app (máx. 9 letras)", "lg_size_hint": "◄ ► Ajustar tamaño   B Atrás", "lg_w": "Blanco", "lg_c": "Contorno", "lg_hint": "Izq/Der Cambiar   A Elegir   B Atrás", "lg_max": "Máximo 9 letras", "lg_fit": "Ajustado al espacio",
        "ic_A": "A · Giro", "ic_B": "B · Latido", "ic_C": "C · Flotar", "ic_D": "D · Campana", "ic_E": "E · Gelatina",
        "ck_A": "A · Aurora", "ck_B": "B · Retro terminal", "ck_C": "C · Pop", "ck_D": "D · Elegante dorado", "ck_E": "E · Neón",
        "cat_support": "Acerca de", "sup_title": "Apoya PockTV", "sup_t1": "PockTV es gratis.", "sup_t2": "Si te gusta, puedes apoyar su desarrollo con una donación voluntaria.", "sup_t3": "Escanea el código con tu celular", "sup_hint": "B Atrás", "about_t2": "Si te gusta, apoya su desarrollo con una donación voluntaria.", "about_ver": "Versión %s", "about_by": "Hecho por PocketApps", "about_hint": "A Elegir   B Atrás", "au_check": "Buscar actualizaciones", "au_checking": "Buscando…", "au_ok": "Estás al día ✓", "au_new": "Actualizar a %s", "au_down": "Descargando… %d%%", "au_inst": "Instalando…", "au_done_btn": "Aceptar", "au_ask": "Hay una versión nueva. ¿Instalar?", "au_done": "Listo. Cierra y abre PockTV.", "au_err_net": "Sin conexión a internet", "au_err_fail": "No se pudo actualizar. Todo sigue igual.",
        "cat_audio": "Audio", "cat_subs": "Subtítulos", "multi_hint": "A Marcar / quitar   B Atrás", "multi_max": "Máximo %d idiomas",
        "row_channels": "Idioma de Canales", "row_lang_movies": "Idioma de Películas", "row_lang_series": "Idioma de Series",
        "set_hint": "A Elegir   B Atrás",
        "row_ui_lang": "Idioma de la interfaz", "row_content": "Idioma de Canales",
        "row_unknown": "Incluir canales sin idioma identificado", "yes": "Sí", "no": "No",
        "row_clock": "Formato de hora", "row_date": "Formato de fecha", "row_dsize": "Tamaño de la fecha", "sf_row": "Estilo de letra", "sf_size": "Tamaño de letra", "sf_A": "DejaVu Sans", "sf_B": "Poppins", "sf_C": "Lora (con serifa)", "sf_D": "DejaVu Mono", "sf_E": "Inter", "move_hint": "▲ ▼ Mover   X Soltar", "set_hint_menu": "A Elegir   X Mover   B Atrás", "row_video": "Modo de pantalla",
        "all": "Todos", "unknown": "Sin identificar", "clock12": "12 horas", "clock24": "24 horas",
        "video_normal": "Normal", "video_estirar": "Pantalla completa", "video_zoom": "Zoom", "video_auto": "Estirar",
        "video_auto_d": "Quita las barras negras de la imagen y llena toda la pantalla",
        "video_normal_d": "Mantiene la proporción (bandas negras)",
        "video_estirar_d": "Estira la imagen a toda la pantalla",
        "video_zoom_d": "Llena la pantalla recortando los bordes",
        "menu_title": "Opciones", "menu_video": "Pantalla", "menu_audio": "Audio", "menu_subs": "Subtítulos",
        "tracks_n": "%d pistas", "tracks_none": "No hay pistas", "subs_off": "Sin subtítulos",
        "subs_bitmap": "(imagen)", "subs_text": "(texto: puede no verse)",
        "row_audio": "Lenguaje de audio", "row_sub1": "Subtítulos - 1er lugar", "row_sub2": "Subtítulos - 2do lugar",
        "aud_pick1": "Audio: elige el #1", "aud_pick2": "Audio: elige el #2", "aud_pick3": "Audio: elige el #3 (el #4 es el restante)",
        "aud_place": "#%d", "sub_none": "Ninguno", "sub_off": "Sin subtítulos",
        "short_lat": "Latino", "short_cas": "Castell.", "short_spa": "Español", "short_eng": "Inglés", "lang_spa": "Español", "lang_lat": "Español Latino", "lang_cas": "Castellano", "lang_eng": "Inglés",
        "video_title": "Video", "video_menu_hint": "Arriba/Abajo: elegir    A: aplicar    B: cancelar",
        "video_session": "Solo para esta reproducción",
        "pick_hint": "A Elegir   B Cancelar", "lists_title": "CAMBIAR DE LISTA",
        "lists_more": "Pon más listas en la carpeta  listas/  (archivos .m3u o .url)",
        "main_list": "Principal", "active": "activa", "exp_left": "Vence el %s · faltan %d días", "exp_dead": "Venció el %s", "exp_none": "Sin fecha de vencimiento", "exp_na": "Vencimiento no disponible", "exp_load": "Consultando vencimiento…",
        "downloading": "Descargando lista...", "reading": "Leyendo lista...", "updating": "Actualizando listas...",
        "wait": "Un momento...",
        "dl_fail": "No pude descargar la lista; uso la guardada.", "no_internet": "Sin internet: conecta el WiFi de la consola",
        "dl_fail_log": "No pude descargar la lista (ver iptv_ui.log)",
        "upd_ok": "Listas actualizadas: %d entradas", "upd_partial": "Actualicé %d de %d listas; el resto falló",
        "upd_none": "Recargué la lista (no hay direcciones .url para descargar)",
        "list_loaded": "Lista cargada: %s (%d entradas)", "list_empty": "La lista %s no tiene entradas",
        "play_fail": "No se pudo reproducir: %s", "no_net": "Sin conexión a internet. Revisa el wifi e inténtalo de nuevo.", "auth_fail": "El servidor rechazó el acceso (401/403): tu cuenta no permite este contenido o hay otra sesión abierta", "no_other": "Ningún otro canal tiene transmisión",
        "see_log": "ver ffplay.log", "no_save_favs": "No pude guardar los favoritos",
        "scrub_total": "Total %s", "scrub_unknown": "Duración desconocida", "scrub_from": "(desde %s)",
        "scrub_keys1": "Izq/Der: 10 s   L1/R1: 1 min   L2/R2: 5 min", "scrub_keys2": "A: reanudar ahora     B: cancelar",
        "am": "a.m.", "pm": "p.m.",
        "days": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
        "months": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                   "septiembre", "octubre", "noviembre", "diciembre"],
        "date_fmt": "{wd}, {d} de {m}",
        "date_fmts": {"A": "{wd} {d} de {m} de {y}", "B": "{wa}, {d} {ma} {y}", "C": "{d:02d}/{mo:02d}/{y}", "D": "{mo:02d}/{d:02d}/{y}", "E": "{d:02d}-{mo:02d}-{y}"},
        "langs": {"es": "Español", "en": "Inglés", "pt": "Portugués", "fr": "Francés", "it": "Italiano",
                  "de": "Alemán", "ar": "Árabe", "tr": "Turco", "ru": "Ruso", "zh": "Chino", "ja": "Japonés",
                  "ko": "Coreano", "nl": "Neerlandés", "pl": "Polaco", "hi": "Hindi", "el": "Griego",
                  "he": "Hebreo", "sv": "Sueco", "ro": "Rumano", "uk": "Ucraniano", "fa": "Persa"},
    },
    "en": {
        "tile_TV": "Live TV", "tile_PELIS": "Movies", "tile_SERIES": "Series", "tile_FAV": "Favorites", "tile_ALL": "Master search",
        "kind_TV": "TV", "kind_PELIS": "Movie", "kind_SERIES": "Series",
        "unit_TV": "channels", "unit_PELIS": "movies", "unit_SERIES": "series", "unit_FAV": "favorites",
        "icon_search": "Master search", "icon_update": "Update Lists", "icon_lists": "Change List", "icon_settings": "Settings",
        "footer_list": "List: %s  ·  %d entries", "footer_keys": "A  Enter      B  Exit",
        "filter_on": "Content language: %s",
        "no_list": "Missing lista.m3u in App/PockTV (or lista.url)",
        "list_hint": "A Play   X Favorite   Y Search   B %s", "list_back": "Back", "list_clear": "Clear search",
        "no_results": 'No results for "%s"', "no_results_hint": "B: clear search    Y: search again",
        "no_favs": "You have no favorites yet", "no_favs_1": "In any list, highlight a channel, category or show and press X",
        "no_favs_2": "to mark it with a star",
        "no_entries": "No entries in this category", "no_entries_hint": "Check your list or the content language in Settings",
        "search_in": "Search in %s", "search_groups": "Search categories", "search_shows": "Search shows", "pause_aspect": "Screen", "pause_fav": "Favorite", "live_txt": "LIVE", "pause_txt": "PAUSED", "play_txt": "PLAYING", "pause_audio": "Audio", "pause_subs": "Subtitles", "pause_subs_s": "Subs", "pause_eps": "Episodes", "pause_next": "Next", "pause_restart": "Restart", "exit_q": "Do you want to quit?", "exit_yes": "Yes", "exit_no": "No", "fav_loose": "Single channels", "fav_loose_hint": "Mark or remove each channel inside its list", "fav_in_group": "Remove it from the favorite category or show", "fav_via_group": "It is a favorite through its category or show: remove it from its own list", "no_group": "No category", "preview_a": "Press « A »", "preview_see": "to watch", "pv_loading": "Loading…", "pv_fail": "Couldn't show", "pv_fail2": "the preview", "pv_nofmpeg": "ffmpeg needed for", "pv_again": "« A » again: full screen", "preview_full": "for full screen", "split_hint": "◀ ▶ column   L/R letter   A Play   X Favorite   Y Search   B Back", "type_name": "Type the name…",
        "kb_space": "Space", "kb_del": "Delete", "kb_go": "Search", "kb_cancel": "Cancel",
        "kb_hint": "A Type   B Delete   X Space   Start / Y Search", "del_ask": "Delete this list?", "quit_ask": "Quit?", "del_main": "The main list can't be deleted here", "del_done": "List deleted: %s", "del_fail": "Couldn't delete the list", "lists_hint": "A Choose   X Delete   B Back",
        "opening": "Opening…", "play_hint": "Up/Down: channel   A: video   Left/Right: -/+10 s   B: back",
        "settings": "SETTINGS", "cat_lang": "Interface Language", "cat_clock": "Clock and Date", "cat_video": "Video",
        "cat_look": "Appearance", "cat_sound": "Sound", "snd_off": "No sound", "snd_suave": "Soft", "snd_cristal": "Crystal", "snd_madera": "Wood", "snd_burbuja": "Bubble", "snd_marimba": "Marimba", "look_cards": "Cards", "look_icons": "Interface Icons",
        "look_clock": "Clock / Date / Wi-Fi", "look_logo": "Logo", "look_fonts": "Section Fonts", "sf_def": "Default · Comic Sans MS", "fx_default": "Default",
        "fx_A": "A · Zoom with shadow", "fx_B": "B · Sweeping shine", "fx_C": "C · Dim the others", "fx_D": "D · Light around the border", "fx_E": "E · Breathing with glow",
        "logo_1": "Flip V2", "logo_2": "Mini Flip", "logo_3": "Mini Plus", "lg_icon": "Icon", "logo_per": "Customize", "lg_text": "Text", "lg_font": "Letter style", "lg_size": "Size",
        "lg_f_A": "Classic", "lg_f_B": "Italic", "lg_f_C": "Elegant", "lg_f_D": "Machine", "lg_f_E": "Modern",
        "lg_kb": "App name (max 9 letters)", "lg_size_hint": "◄ ► Adjust size   B Back", "lg_w": "White", "lg_c": "Outline", "lg_hint": "Left/Right Change   A Select   B Back", "lg_max": "Max 9 letters", "lg_fit": "Fitted to the space",
        "ic_A": "A · Spin", "ic_B": "B · Heartbeat", "ic_C": "C · Float", "ic_D": "D · Bell", "ic_E": "E · Jelly",
        "ck_A": "A · Aurora", "ck_B": "B · Retro terminal", "ck_C": "C · Pop", "ck_D": "D · Elegant gold", "ck_E": "E · Neon",
        "cat_support": "About", "sup_title": "Support PockTV", "sup_t1": "PockTV is free.", "sup_t2": "If you like it, you can support its development with a voluntary donation.", "sup_t3": "Scan the code with your phone", "sup_hint": "B Back", "about_t2": "If you like it, support its development with a voluntary donation.", "about_ver": "Version %s", "about_by": "Made by PocketApps", "about_hint": "A Select   B Back", "au_check": "Check for updates", "au_checking": "Checking…", "au_ok": "You're up to date ✓", "au_new": "Update to %s", "au_down": "Downloading… %d%%", "au_inst": "Installing…", "au_done_btn": "OK", "au_ask": "A new version is available. Install?", "au_done": "Done. Close and reopen PockTV.", "au_err_net": "No internet connection", "au_err_fail": "Update failed. Nothing was changed.",
        "cat_audio": "Audio", "cat_subs": "Subtitles", "multi_hint": "A Mark / unmark   B Back", "multi_max": "Up to %d languages",
        "row_channels": "Channel Language", "row_lang_movies": "Movie Language", "row_lang_series": "Series Language",
        "set_hint": "A Select   B Back",
        "row_ui_lang": "Interface language", "row_content": "Content language",
        "row_unknown": "Include channels with unidentified language", "yes": "Yes", "no": "No",
        "row_clock": "Time format", "row_date": "Date format", "row_dsize": "Date size", "sf_row": "Font style", "sf_size": "Font size", "sf_A": "DejaVu Sans", "sf_B": "Poppins", "sf_C": "Lora (serif)", "sf_D": "DejaVu Mono", "sf_E": "Inter", "move_hint": "▲ ▼ Move   X Drop", "set_hint_menu": "A Select   X Move   B Back", "row_video": "Screen mode",
        "all": "All", "unknown": "Unidentified", "clock12": "12-hour", "clock24": "24-hour",
        "video_normal": "Normal", "video_estirar": "Full screen", "video_zoom": "Zoom", "video_auto": "Stretch",
        "video_auto_d": "Removes the black bars from the picture and fills the whole screen",
        "video_normal_d": "Keeps the aspect ratio (black bars)",
        "video_estirar_d": "Stretches the picture to the whole screen",
        "video_zoom_d": "Fills the screen by cropping the edges",
        "menu_title": "Options", "menu_video": "Screen", "menu_audio": "Audio", "menu_subs": "Subtitles",
        "tracks_n": "%d tracks", "tracks_none": "No tracks", "subs_off": "No subtitles",
        "subs_bitmap": "(image)", "subs_text": "(text: may not show)",
        "row_audio": "Audio language", "row_sub1": "Subtitles - 1st place", "row_sub2": "Subtitles - 2nd place",
        "aud_pick1": "Audio: choose #1", "aud_pick2": "Audio: choose #2", "aud_pick3": "Audio: choose #3 (#4 is the remaining one)",
        "aud_place": "#%d", "sub_none": "None", "sub_off": "No subtitles",
        "short_lat": "Latino", "short_cas": "Castil.", "short_spa": "Spanish", "short_eng": "English", "lang_spa": "Spanish", "lang_lat": "Latin American Spanish", "lang_cas": "Castilian Spanish", "lang_eng": "English",
        "video_title": "Video", "video_menu_hint": "Up/Down: choose    A: apply    B: cancel",
        "video_session": "Only for this playback",
        "pick_hint": "A Select   B Cancel", "lists_title": "CHANGE LIST",
        "lists_more": "Put more lists in the  listas/  folder  (.m3u or .url files)",
        "main_list": "Main", "active": "active", "exp_left": "Expires %s · %d days left", "exp_dead": "Expired on %s", "exp_none": "No expiration date", "exp_na": "Expiration not available", "exp_load": "Checking expiration…",
        "downloading": "Downloading list...", "reading": "Reading list...", "updating": "Updating lists...",
        "wait": "One moment...",
        "dl_fail": "Could not download the list; using the saved one.", "no_internet": "No internet: connect the console to WiFi",
        "dl_fail_log": "Could not download the list (see iptv_ui.log)",
        "upd_ok": "Lists updated: %d entries", "upd_partial": "Updated %d of %d lists; the rest failed",
        "upd_none": "List reloaded (there are no .url links to download)",
        "list_loaded": "List loaded: %s (%d entries)", "list_empty": "The list %s has no entries",
        "play_fail": "Could not play: %s", "no_net": "No internet connection. Check the wifi and try again.", "auth_fail": "Server refused access (401/403): your account may not allow this content, or another session is open", "no_other": "No other channel is streaming",
        "see_log": "see ffplay.log", "no_save_favs": "Could not save favorites",
        "scrub_total": "Total %s", "scrub_unknown": "Unknown duration", "scrub_from": "(from %s)",
        "scrub_keys1": "Left/Right: 10 s   L1/R1: 1 min   L2/R2: 5 min", "scrub_keys2": "A: resume now     B: cancel",
        "am": "AM", "pm": "PM",
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months": ["January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December"],
        "date_fmt": "{wd}, {m} {d}",
        "date_fmts": {"A": "{wd}, {m} {d}, {y}", "B": "{wa}, {ma} {d}, {y}", "C": "{d:02d}/{mo:02d}/{y}", "D": "{mo:02d}/{d:02d}/{y}", "E": "{d:02d}-{mo:02d}-{y}"},
        "langs": {"es": "Spanish", "en": "English", "pt": "Portuguese", "fr": "French", "it": "Italian",
                  "de": "German", "ar": "Arabic", "tr": "Turkish", "ru": "Russian", "zh": "Chinese", "ja": "Japanese",
                  "ko": "Korean", "nl": "Dutch", "pl": "Polish", "hi": "Hindi", "el": "Greek",
                  "he": "Hebrew", "sv": "Swedish", "ro": "Romanian", "uk": "Ukrainian", "fa": "Persian"},
    },
}


try:
    from i18n_x import PT, FR, DE
    S["pt"], S["fr"], S["de"] = PT, FR, DE
except Exception:
    pass
UI_LANGS = [c for c in ("es", "en", "pt", "fr", "de") if c in S]
NATIVE = {"es": "Español", "en": "English", "pt": "Português", "fr": "Français", "de": "Deutsch"}


def set_lang(code):
    LANG[0] = code if code in S else "es"


def get_lang():
    return LANG[0]


def T(key, *args):
    s = S[LANG[0]].get(key)
    if s is None:
        s = S["en"].get(key) if LANG[0] != "es" else None
    if s is None:
        s = S["es"].get(key, key)
    if args and isinstance(s, str):
        return s % args
    return s


def date_text(wday, mday, month, year=None, code="default"):
    """Fecha para mostrar bajo el reloj: code = default, A..E (formatos del menu Reloj y Fecha)."""
    import time as _t
    if year is None:
        year = _t.localtime().tm_year
    d = S[LANG[0]]
    fmt = d.get("date_fmt") or S["en"]["date_fmt"]
    if code != "default":
        fmt = (d.get("date_fmts") or S["en"]["date_fmts"]).get(code) or fmt
    wd, mn = d["days"][wday], d["months"][month - 1]
    return fmt.format(wd=wd, wa=wd[:3], d=mday, m=mn, ma=mn[:3], mo=month, y=year)


def lang_name(code):
    lg = S[LANG[0]].get("langs") or S["en"]["langs"]
    return lg.get(code) or S["en"]["langs"].get(code) or S["es"]["langs"].get(code) or code.upper()
