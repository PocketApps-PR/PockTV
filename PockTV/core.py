"""Lectura de listas M3U y clasificacion en TV / PELIS / SERIES (sin dependencias graficas)."""
import json
import os
import re
import unicodedata

CATS = ("TV", "PELIS", "SERIES")


def norm(s):
    """Minusculas y sin acentos, para buscar 'accion' y encontrar 'Acción'."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

DEFAULT_KW_SERIES = "serie novela anime temporada season"
DEFAULT_KW_PELIS = "peli movie film vod cine pelicula película"

_RE_GROUP = re.compile(r'group-title="([^"]*)"')
_RE_TVGLANG = re.compile(r'tvg-language="([^"]*)"', re.IGNORECASE)
_RE_TVGID = re.compile(r'tvg-id="([^"]*)"', re.IGNORECASE)
_RE_TVGCOUNTRY = re.compile(r'tvg-country="([^"]*)"', re.IGNORECASE)
_RE_EPISODE = re.compile(r"s\d+ ?e\d+", re.IGNORECASE)


class Entry(object):
    __slots__ = ("name", "group", "url", "cat", "nname", "fkey", "lang")

    def __init__(self, name, group, url, cat, lang=""):
        self.lang = lang
        self.name = name
        self.group = group
        self.url = url
        self.cat = cat
        self.nname = norm(name)
        # Clave del favorito: categoria + nombre (la direccion puede cambiar al refrescar la lista)
        self.fkey = cat + "\t" + name


# ---------------- Idioma del contenido (deteccion aproximada) ----------------
# Las listas M3U no traen un campo oficial de "idioma del audio": se deduce de
# tvg-language, etiquetas como "ES|" o "[EN]", el pais del tvg-id, el nombre del grupo
# y palabras del nombre. Lo que no se pueda deducir queda "sin identificar".
LANG_WORDS = {
    "es": "spanish espanol castellano latino latina latinoamerica hispano hispana spa esp",
    "en": "english ingles eng",
    "pt": "portuguese portugues brasil brazil brasileiro por",
    "fr": "french frances francais francaise fra fre",
    "it": "italian italiano italia ita",
    "de": "german aleman deutsch ger deu",
    "ar": "arabic arabe ara",
    "tr": "turkish turco turkce tur",
    "ru": "russian ruso rus",
    "zh": "chinese chino mandarin cantonese",
    "ja": "japanese japones jpn",
    "ko": "korean coreano kor",
    "nl": "dutch holandes neerlandes",
    "pl": "polish polaco polski",
    "hi": "hindi",
    "el": "greek griego",
    "he": "hebrew hebreo",
    "sv": "swedish sueco",
    "ro": "romanian rumano",
    "uk": "ukrainian ucraniano",
    "fa": "persian persa farsi",
}
_WORD2LANG = {}
for _code, _ws in LANG_WORDS.items():
    for _w in _ws.split():
        _WORD2LANG[_w] = _code
# Palabras demasiado cortas/ambiguas: solo valen como etiqueta (ES|, [EN], ...), no sueltas en el nombre
_TAG_ONLY = set("spa esp eng por fra fre ita ger deu ara tur rus jpn kor".split())
_TAGS = {"es": "es esp spa lat latam", "en": "en eng uk us usa", "pt": "pt por br", "fr": "fr fra fre",
         "it": "it ita", "de": "de ger deu", "ar": "ar ara", "tr": "tr tur", "ru": "ru rus",
         "zh": "cn zh chi", "ja": "jp ja jpn", "ko": "kr ko kor", "nl": "nl", "pl": "pl", "hi": "hi in",
         "el": "gr el", "he": "il he", "sv": "se sv", "ro": "ro", "uk": "ua", "fa": "ir"}
_TAG2LANG = {}
for _code, _ws in _TAGS.items():
    for _w in _ws.split():
        _TAG2LANG[_w] = _code
_TAG2LANG.pop("us", None)   # "US|" es un pais, no un idioma
_TAG2LANG.pop("usa", None)
_TAG2LANG.pop("uk", None)
_TAG2LANG.pop("in", None)
_RE_TAG = re.compile(r"(?:^|[\[\(\|])\s*([a-z]{2,5})\s*(?:[\]\)\|:]|\s[-\u2013]\s)")
_RE_TAG_END = re.compile(r"[\[\(]\s*([a-z]{2,5})\s*[\]\)]\s*$")
_RE_WORDS = re.compile(r"[a-z]+")
_COUNTRY_LANG = {}
for _code, _ws in {
    "es": "es mx ar co cl pe ve ec gt cu bo do hn py sv ni cr pa uy pr gq",
    "en": "gb uk au nz ie za sg",
    "pt": "br pt ao mz", "fr": "fr be lu mc", "it": "it sm va", "de": "de at li",
    "ar": "sa ae eg iq jo kw lb ly ma qa sy tn ye dz om bh sd", "tr": "tr", "ru": "ru by kz",
    "zh": "cn tw hk", "ja": "jp", "ko": "kr", "nl": "nl", "pl": "pl", "hi": "in", "el": "gr",
    "he": "il", "sv": "se", "ro": "ro md", "uk": "ua", "fa": "ir",
}.items():
    for _w in _ws.split():
        _COUNTRY_LANG[_w] = _code
_COUNTRY_NAMES = {
    "puerto rico": "es", "mexico": "es", "argentina": "es", "spain": "es", "espana": "es", "colombia": "es",
    "chile": "es", "peru": "es", "venezuela": "es", "ecuador": "es", "guatemala": "es", "cuba": "es",
    "bolivia": "es", "dominicana": "es", "honduras": "es", "paraguay": "es", "salvador": "es",
    "nicaragua": "es", "costa rica": "es", "panama": "es", "uruguay": "es",
    "united kingdom": "en", "australia": "en", "new zealand": "en", "ireland": "en", "united states": "en",
    "brazil": "pt", "brasil": "pt", "portugal": "pt", "france": "fr", "francia": "fr", "italy": "it",
    "germany": "de", "alemania": "de", "turkey": "tr", "turquia": "tr", "russia": "ru", "rusia": "ru",
    "japan": "ja", "japon": "ja", "korea": "ko", "china": "zh", "india": "hi", "greece": "el",
    "poland": "pl", "polonia": "pl", "netherlands": "nl", "arab": "ar", "arabia": "ar",
}
_ES_HINT = set("noticias deportes canal cine peliculas novelas infantil musica television telemundo univision "
               "unimas estrella azteca televisa galavision tudn caracol rcn antena telecinco sexta iglesia "
               "cristiano cristiana tele vision pelicula serie series dibujos".split())
_EN_HINT = set("news sports movies movie kids channel network music entertainment weather shopping comedy "
               "drama action cartoon cartoons classic classics the".split())


def detect_lang(name, group="", tvg_lang="", tvg_id="", tvg_country=""):
    """Codigo de idioma ('es', 'en', ...) o '' si no se puede deducir."""
    # 1) tvg-language explicito
    if tvg_lang:
        for w in _RE_WORDS.findall(norm(tvg_lang)):
            if w in _WORD2LANG:
                return _WORD2LANG[w]
    nn, ng = norm(name), norm(group)
    # 2) etiquetas "ES|", "[EN]", "(ES)" al inicio del nombre/grupo o al final del nombre
    for text, end in ((ng, False), (nn, False), (nn, True)):
        m = (_RE_TAG_END if end else _RE_TAG).search(text)
        if m and m.group(1) in _TAG2LANG:
            return _TAG2LANG[m.group(1)]
    # 3) palabras de idioma en el grupo o nombre ("Spanish", "Latino", "English")
    for text in (ng, nn):
        for w in _RE_WORDS.findall(text):
            if w in _WORD2LANG and w not in _TAG_ONLY and w not in ("por", "uk"):
                return _WORD2LANG[w]
    # 4) pais del tvg-id (.mx, .pr, ...) o tvg-country
    cc = ""
    if tvg_id:
        m = re.search(r"\.([a-z]{2})(?:@|$)", tvg_id.lower())
        if m:
            cc = m.group(1)
    if not cc and tvg_country:
        cc = norm(tvg_country).split(";")[0].strip()[:2]
    if cc and cc not in ("us", "ca", "ch", "be") and cc in _COUNTRY_LANG:
        return _COUNTRY_LANG[cc]
    # 5) nombre de pais en el grupo
    for k, v in _COUNTRY_NAMES.items():
        if k in ng:
            if v == "en" and "united states" in ng:
                break
            return v
    # 6) palabras tipicas del nombre/grupo
    ws = _RE_WORDS.findall(nn + " " + ng)
    es = sum(1 for w in ws if w in _ES_HINT)
    en = sum(1 for w in ws if w in _EN_HINT)
    if es > en:
        return "es"
    if en > es:
        return "en"
    if cc == "us":
        return "en"
    return ""


def langs_present(entries):
    """Conteo {codigo: cantidad} de los idiomas detectados ('' = sin identificar)."""
    out = {}
    for e in entries:
        out[e.lang] = out.get(e.lang, 0) + 1
    return out


def classify(group, url, name, kw_series=DEFAULT_KW_SERIES, kw_pelis=DEFAULT_KW_PELIS):
    """Misma logica que la app de Ports: direccion, luego grupo, luego nombre."""
    u = url.lower()
    if "/series/" in u:
        return "SERIES"
    if "/movie/" in u or "/movies/" in u:
        return "PELIS"
    # sin /movie/ ni /series/ y sin extension de archivo de video = canal en vivo, aunque el grupo diga "Cine"
    last = u.split("?", 1)[0].split("#", 1)[0].rsplit("/", 1)[-1]
    if ("." not in last or last.rsplit(".", 1)[-1] == "ts") and u.startswith(("http://", "https://")):
        return "TV"
    g = group.lower()
    for w in kw_series.split():
        if w.lower() in g:
            return "SERIES"
    for w in kw_pelis.split():
        if w.lower() in g:
            return "PELIS"
    if _RE_EPISODE.search(name):
        return "SERIES"
    return "TV"


def _name_comma(line):
    """Posicion de la coma que separa los atributos del nombre: la primera que NO esta entre comillas
    (las direcciones de logos pueden traer comas dentro, p. ej. h_720,q_75)."""
    inq = False
    for i, ch in enumerate(line):
        if ch == '"':
            inq = not inq
        elif ch == "," and not inq:
            return i
    return line.find(",")


def parse_m3u(text, kw_series=DEFAULT_KW_SERIES, kw_pelis=DEFAULT_KW_PELIS, prog=None):
    """Devuelve la lista de Entry. Ignora lineas que no parezcan una direccion de stream.
    prog(frac): se llama de vez en cuando con el avance 0..1 (barra de carga)."""
    entries = []
    name = ""
    group = ""
    tl = tid = tc = ""
    lines = text.replace("\r", "").split("\n")
    nl = max(1, len(lines))
    for li, raw in enumerate(lines):
        if prog is not None and li % 2000 == 0:
            try:
                prog(li / float(nl))
            except Exception:
                pass
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            comma = _name_comma(line)
            name = line[comma + 1:].strip() if comma >= 0 else ""
            m = _RE_GROUP.search(line)
            group = m.group(1).strip() if m else ""
            mm = _RE_TVGLANG.search(line)
            tl = mm.group(1) if mm else ""
            mm = _RE_TVGID.search(line)
            tid = mm.group(1) if mm else ""
            mm = _RE_TVGCOUNTRY.search(line)
            tc = mm.group(1) if mm else ""
            continue
        if line.startswith("#"):
            continue
        if "://" not in line:
            name = ""
            group = ""
            tl = tid = tc = ""
            continue
        cat = classify(group, line, name, kw_series, kw_pelis)
        entries.append(Entry(name or "Sin nombre", group, line, cat, detect_lang(name, group, tl, tid, tc)))
        name = ""
        group = ""
        tl = tid = tc = ""
    if prog is not None:
        try:
            prog(1.0)                                 # la barra llega al 100 %
        except Exception:
            pass
    return entries


def load_file(path, kw_series=DEFAULT_KW_SERIES, kw_pelis=DEFAULT_KW_PELIS, prog=None):
    with open(path, "rb") as f:
        text = f.read().decode("utf-8", "replace")
    return parse_m3u(text, kw_series, kw_pelis, prog)


def split_by_cat(entries):
    out = {c: [] for c in CATS}
    for e in entries:
        out[e.cat].append(e)
    return out


def read_conf(path):
    """Lee un archivo KEY="valor" (el mismo que puede leer sh). Devuelve dict de str."""
    conf = {}
    try:
        with open(path, "rb") as f:
            for raw in f.read().decode("utf-8", "replace").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                conf[k.strip()] = v
    except (IOError, OSError):
        pass
    return conf


def filter_entries(items, query):
    """Busca por nombre: todas las palabras escritas deben aparecer (sin importar acentos ni mayusculas)."""
    words = norm(query).split()
    if not words:
        return list(items)
    return [e for e in items if all(w in e.nname for w in words)]


def load_favs(path):
    """Favoritos guardados: conjunto de claves (categoria + nombre)."""
    try:
        with open(path, "rb") as f:
            data = json.loads(f.read().decode("utf-8", "replace"))
        return set(k for k in data if isinstance(k, str))
    except Exception:
        return set()


def save_favs(path, favs):
    """Guarda de forma segura (archivo temporal y reemplazo). Devuelve True si salio bien."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(json.dumps(sorted(favs), ensure_ascii=False).encode("utf-8"))
        os.replace(tmp, path)
        return True
    except Exception:
        return False
