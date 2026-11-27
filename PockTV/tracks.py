"""Pistas de audio y subtitulos: leer lo que ffplay informa, clasificar idiomas y elegir
segun las prioridades del usuario. Logica pura (sin SDL), probada aparte."""
import re

STREAM_RE = re.compile(r"Stream #\d+:(\d+)(?:\[[^\]]*\])?(?:\(([^)]*)\))?: (Audio|Subtitle|Video): (.*)")
TITLE_RE = re.compile(r"^\s+title\s*:\s*(.+?)\s*$")
BITMAP_SUBS = ("dvd_subtitle", "dvdsub", "hdmv_pgs_subtitle", "pgssub", "dvb_subtitle", "dvbsub", "xsub")

AUDIO_CATS = ("lat", "cas", "spa", "eng")
# Idiomas ofrecidos en Ajustes (despues de "Todos"): Español, Español Latino, Castellano, Inglés y los demas.
LANG_ORDER = ("spa", "lat", "cas", "eng", "por", "fre", "ita", "ger", "jpn", "kor", "chi", "rus", "ara", "tur",
              "dut", "pol", "hin", "gre", "heb", "swe", "dan", "nor", "fin", "ukr", "rum", "tha", "vie", "ind", "per")
SUB_CODES = ("none",) + LANG_ORDER
ALIASES = {"es": "spa", "esp": "spa", "en": "eng", "pt": "por", "fr": "fre", "fra": "fre", "it": "ita",
           "de": "ger", "deu": "ger", "ja": "jpn", "jp": "jpn", "ko": "kor", "zh": "chi", "zho": "chi",
           "ru": "rus", "ar": "ara", "tr": "tur", "nl": "dut", "nld": "dut", "pl": "pol", "hi": "hin",
           "el": "gre", "ell": "gre", "he": "heb", "sv": "swe", "da": "dan", "no": "nor", "nob": "nor",
           "fi": "fin", "uk": "ukr", "ro": "rum", "ron": "rum", "th": "tha", "vi": "vie", "id": "ind",
           "fa": "per", "fas": "per"}
_N = {  # codigo: (es, en, pt, fr, de)
    "spa": ("Español", "Spanish", "Espanhol", "Espagnol", "Spanisch"),
    "lat": ("Español Latino", "Latin American Spanish", "Espanhol Latino", "Espagnol latino", "Lateinam. Spanisch"),
    "cas": ("Castellano", "Castilian Spanish", "Castelhano", "Castillan", "Kastilisch"),
    "eng": ("Inglés", "English", "Inglês", "Anglais", "Englisch"),
    "por": ("Portugués", "Portuguese", "Português", "Portugais", "Portugiesisch"),
    "fre": ("Francés", "French", "Francês", "Français", "Französisch"),
    "ita": ("Italiano", "Italian", "Italiano", "Italien", "Italienisch"),
    "ger": ("Alemán", "German", "Alemão", "Allemand", "Deutsch"),
    "jpn": ("Japonés", "Japanese", "Japonês", "Japonais", "Japanisch"),
    "kor": ("Coreano", "Korean", "Coreano", "Coréen", "Koreanisch"),
    "chi": ("Chino", "Chinese", "Chinês", "Chinois", "Chinesisch"),
    "rus": ("Ruso", "Russian", "Russo", "Russe", "Russisch"),
    "ara": ("Árabe", "Arabic", "Árabe", "Arabe", "Arabisch"),
    "tur": ("Turco", "Turkish", "Turco", "Turc", "Türkisch"),
    "dut": ("Holandés", "Dutch", "Holandês", "Néerlandais", "Niederländisch"),
    "pol": ("Polaco", "Polish", "Polonês", "Polonais", "Polnisch"),
    "hin": ("Hindi", "Hindi", "Hindi", "Hindi", "Hindi"),
    "gre": ("Griego", "Greek", "Grego", "Grec", "Griechisch"),
    "heb": ("Hebreo", "Hebrew", "Hebraico", "Hébreu", "Hebräisch"),
    "swe": ("Sueco", "Swedish", "Sueco", "Suédois", "Schwedisch"),
    "dan": ("Danés", "Danish", "Dinamarquês", "Danois", "Dänisch"),
    "nor": ("Noruego", "Norwegian", "Norueguês", "Norvégien", "Norwegisch"),
    "fin": ("Finés", "Finnish", "Finlandês", "Finnois", "Finnisch"),
    "ukr": ("Ucraniano", "Ukrainian", "Ucraniano", "Ukrainien", "Ukrainisch"),
    "rum": ("Rumano", "Romanian", "Romeno", "Roumain", "Rumänisch"),
    "tha": ("Tailandés", "Thai", "Tailandês", "Thaï", "Thailändisch"),
    "vie": ("Vietnamita", "Vietnamese", "Vietnamita", "Vietnamien", "Vietnamesisch"),
    "ind": ("Indonesio", "Indonesian", "Indonésio", "Indonésien", "Indonesisch"),
    "per": ("Persa", "Persian", "Persa", "Persan", "Persisch"),
    "und": ("Desconocido", "Unknown", "Desconhecido", "Inconnu", "Unbekannt"),
    "none": ("Ninguno", "None", "Nenhum", "Aucun", "Keine"),
}
NAMES = {lg: {k: v[i] for k, v in _N.items()} for i, lg in enumerate(("es", "en", "pt", "fr", "de"))}
RE_CAS = re.compile(r"castell|castil|espa[nñ]a|spain|\bes-es\b|iberi|peninsul|\bcast\b")
RE_LAT = re.compile(r"latin|\blat\b|latam|mexic|419|hispano|\bes-mx\b")
RE_ENG = re.compile(r"engl|ingl")


def lang_code(lang, title=""):
    """Codigo normalizado: lat / cas / spa (español sin variante) / eng / otros ISO / und."""
    lang = (lang or "").lower().strip()
    text = (lang + " " + (title or "")).lower()
    is_spa = lang in ("spa", "es", "esp") or "español" in text or "espanol" in text or "spanish" in text
    if RE_CAS.search(text):
        return "cas"
    if RE_LAT.search(text) and (is_spa or lang in ("", "und", "lat")):
        return "lat"
    if is_spa:
        return "spa"
    if lang in ("eng", "en") or RE_ENG.search(text):
        return "eng"
    code = ALIASES.get(lang, lang)
    return code if code in SUB_CODES else (code or "und")


def parse_line(info, line):
    """Alimenta info['streams'] con una linea de la salida de ffplay."""
    mt = STREAM_RE.search(line)
    if mt:
        idx = int(mt.group(1))
        desc = mt.group(4)
        codec = desc.split(",")[0].split("(")[0].strip().lower()
        s = {"idx": idx, "type": mt.group(3), "lang": (mt.group(2) or "").lower(), "title": "",
             "codec": codec, "desc": desc, "default": "(default)" in desc}
        streams = info.setdefault("streams", [])
        for i, old in enumerate(streams):
            if old["idx"] == idx:
                streams[i] = s
                break
        else:
            streams.append(s)
        info["_last"] = s
        return True
    mt = TITLE_RE.match(line)
    if mt and info.get("_last") is not None and not info["_last"]["title"]:
        info["_last"]["title"] = mt.group(1)
        return True
    if line.startswith(("Input #", "Output #")):
        info["_last"] = None
    return False


def audios(streams):
    return [s for s in (streams or []) if s["type"] == "Audio"]


def subs(streams):
    return [s for s in (streams or []) if s["type"] == "Subtitle"]


def audio_match(want, code):
    if want == "spa":
        return code in ("spa", "lat", "cas")
    return code == want


def pick_audio(streams, prio):
    """Indice (de ffplay) de la pista de audio segun la lista de prioridades, o None si no hay que cambiar."""
    aus = audios(streams)
    prio = [p for p in (prio or []) if p != "all"]
    if len(aus) < 2 or not prio:
        return None
    cats = [(s["idx"], lang_code(s["lang"], s["title"])) for s in aus]
    for p in prio:
        for idx, c in cats:                      # primero coincidencia exacta
            if c == p:
                return idx
        for idx, c in cats:                      # "Español" acepta cualquier variante
            if audio_match(p, c):
                return idx
    return None


def sub_matches(want, code):
    if want == "spa":
        return code in ("spa", "lat", "cas")
    if want == "lat":
        return code in ("lat", "spa")
    if want == "cas":
        return code in ("cas", "spa")
    return code == want


def pick_sub(streams, wants):
    """'off' (sin subtitulos), un indice de ffplay, o None si el video no trae subtitulos."""
    ss = subs(streams)
    if not ss:
        return None
    for want in (wants or []):
        if want in ("all", "none"):
            continue
        for s in ss:
            if sub_matches(want, lang_code(s["lang"], s["title"])):
                return s["idx"]
    return "off"


def is_bitmap(s):
    return s["codec"] in BITMAP_SUBS


def sub_ordinal(streams, idx):
    for n, s in enumerate(subs(streams)):
        if s["idx"] == idx:
            return n
    return 0


def name_of(code, lang="es"):
    return NAMES.get(lang, NAMES["es"]).get(code, code)


def label(s, ui_lang="es"):
    """Texto de una pista para mostrar: (titulo, detalle)."""
    code = lang_code(s["lang"], s["title"])
    base = name_of(code, ui_lang) if code != "und" else (s["lang"] or name_of("und", ui_lang))
    t = s["title"]
    if t and t.lower() not in base.lower() and len(t) < 40:
        base = "%s – %s" % (base, t)
    return base, s["codec"] + (" · " + _ch(s["desc"]) if _ch(s["desc"]) else "")


def _ch(desc):
    m = re.search(r"\b(mono|stereo|5\.1|7\.1|2\.0)\b", desc)
    return m.group(1) if m else ""
