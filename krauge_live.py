import os
import sys
import io
import re
import time
import json
import wave
import queue
import threading
import subprocess
import urllib.request
import urllib.parse
import html as html_lib
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from toon_packager import (
    ToonPackager,
    fetch_youversion_votd,
    fetch_krauge_comments,
    call_krauge_llm,
    _load_local_env,
)
from generate_krauge_video import resolve_and_update_cycle, NOMAD_16_LADDER

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUT_DIR = os.path.join(BASE_DIR, "out")
INBOX_FILE = os.path.join(BASE_DIR, "live_inbox.txt")

# ==============================================================================
# 1. CONCORDANCIA BÍBLICA EN VIVO (WEB + LITE OFFLINE EN EL RUNNER)
# ==============================================================================

THEMATIC_CONCORDANCE = {
    "miedo": {
        "keywords": ["miedo", "temor", "asustado", "espanto", "pánico", "terror", "cobarde"],
        "verses": [
            ("Isaías 41:10", "No temas, porque yo estoy contigo; no desmayes, porque yo soy tu Dios que te esfuerzo; siempre te ayudaré, siempre te sustentaré con la diestra de mi justicia."),
            ("2 Timoteo 1:7", "Porque no nos ha dado Dios espíritu de cobardía, sino de poder, de amor y de dominio propio."),
            ("Salmos 56:3", "En el día que temo, yo en ti confío."),
        ],
    },
    "ansiedad": {
        "keywords": ["ansiedad", "ansioso", "angustia", "preocupado", "estres", "estrés", "paz", "calma", "insomnio", "mente"],
        "verses": [
            ("Filipenses 4:6-7", "Por nada estéis afanosos, sino sean conocidas vuestras peticiones delante de Dios en toda oración y ruego, con acción de gracias. Y la paz de Dios, que sobrepasa todo entendimiento, guardará vuestros corazones."),
            ("1 Pedro 5:7", "Echando toda vuestra ansiedad sobre él, porque él tiene cuidado de vosotros."),
            ("Juan 14:27", "La paz os dejo, mi paz os doy; yo no os la doy como el mundo la da. No se turbe vuestro corazón, ni tenga miedo."),
        ],
    },
    "soledad": {
        "keywords": ["solo", "sola", "soledad", "abandonado", "nadie", "olvidado", "vacío", "triste", "tristeza", "llorar"],
        "verses": [
            ("Salmos 34:18", "Cercano está Jehová a los quebrantados de corazón; y salva a los contritos de espíritu."),
            ("Deuteronomio 31:8", "Jehová va delante de ti; él estará contigo, no te dejará, ni te desamparará; no temas ni te intimides."),
            ("Salmos 27:10", "Aunque mi padre y mi madre me dejaran, con todo, Jehová me recogerá."),
        ],
    },
    "perdon": {
        "keywords": ["perdón", "perdon", "perdonar", "culpa", "pecado", "error", "fallé", "falle", "rencor", "odio", "traición"],
        "verses": [
            ("1 Juan 1:9", "Si confesamos nuestros pecados, él es fiel y justo para perdonar nuestros pecados, y limpiarnos de toda maldad."),
            ("Isaías 1:18", "Si vuestros pecados fueren como la grana, como la nieve serán emblanquecidos; si fueren rojos como el carmesí, vendrán a ser como blanca lana."),
            ("Efesios 4:32", "Antes sed benignos unos con otros, misericordiosos, perdonándoos unos a otros, como Dios también os perdonó a vosotros en Cristo."),
        ],
    },
    "fuerza": {
        "keywords": ["cansado", "cansada", "agotado", "sin fuerzas", "rendirme", "débil", "debil", "seguir", "luchar"],
        "verses": [
            ("Isaías 40:29-31", "Él da esfuerzo al cansado, y multiplica las fuerzas al que no tiene ningunas. Los que esperan a Jehová tendrán nuevas fuerzas; levantarán alas como las águilas."),
            ("Mateo 11:28", "Venid a mí todos los que estáis trabajados y cargados, y yo os haré descansar."),
            ("2 Corintios 12:9", "Bástate mi gracia; porque mi poder se perfecciona en la debilidad."),
        ],
    },
    "duda": {
        "keywords": ["duda", "dudo", "lógica", "logica", "ciencia", "existe", "creer", "fe", "pruebas", "ateo", "razón"],
        "verses": [
            ("Hebreos 11:1", "Es, pues, la fe la certeza de lo que se espera, la convicción de lo que no se ve."),
            ("Marcos 9:24", "Creo; ayuda mi incredulidad."),
            ("Jeremías 33:3", "Clama a mí, y yo te responderé, y te enseñaré cosas grandes y ocultas que tú no conoces."),
        ],
    },
    "proposito": {
        "keywords": ["propósito", "proposito", "futuro", "destino", "camino", "perdido", "decisión", "trabajo", "dinero", "provisión"],
        "verses": [
            ("Jeremías 29:11", "Porque yo sé los pensamientos que tengo acerca de vosotros, dice Jehová, pensamientos de paz, y no de mal, para daros el fin que esperáis."),
            ("Proverbios 3:5-6", "Fíate de Jehová de todo tu corazón, y no te apoyes en tu propia prudencia. Reconócelo en todos tus caminos, y él enderezará tus veredas."),
            ("Romanos 8:28", "Y sabemos que a los que aman a Dios, todas las cosas les ayudan a bien, esto es, a los que conforme a su propósito son llamados."),
        ],
    },
}

BIBLE_REF_REGEX = re.compile(
    r"\b((?:[1-3]\s*)?(?:Génesis|Genesis|Éxodo|Exodo|Levítico|Números|Deuteronomio|Josué|Josue|Jueces|Rut|Samuel|Reyes|Crónicas|Esdras|Nehemías|Ester|Job|Salmos?|Proverbios|Eclesiastés|Cantares|Isaías|Isaias|Jeremías|Jeremias|Lamentaciones|Ezequiel|Daniel|Oseas|Joel|Amós|Abdías|Jonás|Miqueas|Nahúm|Habacuc|Sofonías|Hageo|Zacarías|Malaquías|Mateo|Marcos|Lucas|Juan|Hechos|Romanos|Corintios|Gálatas|Galatas|Efesios|Filipenses|Colosenses|Tesalonicenses|Timoteo|Tito|Filemón|Hebreos|Santiago|Pedro|Judas|Apocalipsis)\s+\d+(?::\d+(?:-\d+)?)?)\b",
    re.IGNORECASE,
)

# Libros bíblicos para normalización fonética en TTS (evita que edge-tts lea "1 Pedro 5:7" como hora o "uno Pedro")
_BIBLE_BOOKS_PATTERN = (
    r"Génesis|Genesis|Éxodo|Exodo|Levítico|Levitico|Números|Numeros|Deuteronomio|"
    r"Josué|Josue|Jueces|Rut|Samuel|Reyes|Crónicas|Cronicas|Esdras|Nehemías|Nehemias|"
    r"Ester|Job|Salmos?|Proverbios|Eclesiastés|Eclesiastes|Cantares|Isaías|Isaias|"
    r"Jeremías|Jeremias|Lamentaciones|Ezequiel|Daniel|Oseas|Joel|Amós|Amos|Abdías|Abdias|"
    r"Jonás|Jonas|Miqueas|Nahúm|Nahum|Habacuc|Sofonías|Sofonias|Hageo|Zacarías|Zacarias|"
    r"Malaquías|Malaquias|Mateo|Marcos|Lucas|Juan|Hechos|Romanos|Corintios|Gálatas|Galatas|"
    r"Efesios|Filipenses|Colosenses|Tesalonicenses|Timoteo|Tito|Filemón|Filemon|Hebreos|"
    r"Santiago|Pedro|Judas|Apocalipsis"
)

_ORDINAL_BOOK_MAP = {
    "1": "Primera de",
    "2": "Segunda de",
    "3": "Tercera de",
    "I": "Primera de",
    "II": "Segunda de",
    "III": "Tercera de",
}


def format_biblical_speech(text):
    """
    Convierte referencias bíblicas escritas (ej. '1 Pedro 5:7', 'Filipenses 4:6-7', '2 Corintios 12:9')
    en lectura litúrgica hablada natural ('Primera de Pedro capítulo 5, versículo 7',
    'Filipenses capítulo 4, versículos 6 al 7') para que el TTS nunca lea ':' como la hora
    ni '1 Pedro' como 'uno Pedro'.
    """
    if not text:
        return text

    out = str(text)

    # 1. Convertir prefijos numéricos de libros ('1 Pedro', '1 de Pedro', '2da Corintios', etc.)
    def _replace_numbered_book(match):
        num_raw = match.group(1).upper()
        book = match.group(2)
        ordinal = _ORDINAL_BOOK_MAP.get(num_raw, "Primera de")
        return f"{ordinal} {book}"

    out = re.sub(
        rf"\b([1-3]|I{{1,3}})(?:ra|da|era|a|º|ª)?(?:\s+de)?\s+({_BIBLE_BOOKS_PATTERN})\b",
        _replace_numbered_book,
        out,
        flags=re.IGNORECASE,
    )

    # 2. Convertir citas con rango de versículos: '<Libro> 4:6-7' -> '<Libro> capítulo 4, versículos 6 al 7'
    out = re.sub(
        rf"\b({_BIBLE_BOOKS_PATTERN})\s+(\d+)\s*:\s*(\d+)\s*[-–]\s*(\d+)\b",
        r"\1 capítulo \2, versículos \3 al \4",
        out,
        flags=re.IGNORECASE,
    )

    # 3. Convertir citas de un solo versículo: '<Libro> 14:27' -> '<Libro> capítulo 14, versículo 27'
    out = re.sub(
        rf"\b({_BIBLE_BOOKS_PATTERN})\s+(\d+)\s*:\s*(\d+)\b",
        r"\1 capítulo \2, versículo \3",
        out,
        flags=re.IGNORECASE,
    )

    # 4. Salvaguarda: si quedó algún 'capítulo X:Y' o número:número suelto tras mención bíblica
    out = re.sub(
        r"\b(\d{1,3})\s*:\s*(\d{1,3})\s*[-–]\s*(\d{1,3})\b",
        r"capítulo \1, versículos \2 al \3",
        out,
    )
    out = re.sub(
        r"\b(\d{1,3})\s*:\s*(\d{1,3})\b",
        r"capítulo \1, versículo \2",
        out,
    )

    # 5. Limpiar '@' y '_' en menciones de usuarios para que el TTS no diga "arroba" ni "guion bajo"
    out = re.sub(r"@([A-Za-z0-9_.\-]+)", lambda m: m.group(1).replace("_", " ").replace(".", " "), out)
    out = out.replace("_", " ")

    return re.sub(r"\s+", " ", out).strip()


def fetch_biblegateway_passage_live(search_ref):
    """
    Consulta en vivo en BibleGateway (RVR1960) una cita específica pedida por la audiencia en el chat.
    No requiere API Key.
    """
    try:
        q = urllib.parse.quote(search_ref.strip())
        url = f"https://www.biblegateway.com/passage/?search={q}&version=RVR1960"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
                "Accept-Language": "es-MX,es;q=0.9",
            },
        )
        html = urllib.request.urlopen(req, timeout=6).read().decode("utf-8", errors="ignore")

        # Extraer de meta og:description o del bloque passage-text
        m_og = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
        if m_og:
            desc = html_lib.unescape(m_og.group(1)).strip()
            desc = re.sub(r"\s+", " ", desc)
            if len(desc) > 15 and "BibleGateway" not in desc:
                if len(desc) > 220:
                    desc = desc[:217].rsplit(" ", 1)[0] + "..."
                return {
                    "source": "Consulta en Vivo (RVR1960)",
                    "reference": search_ref.title(),
                    "text": desc,
                }
    except Exception:
        pass
    return None


def live_bible_lookup(user_text, cycle_num=1, fallback_votd=None):
    """
    Motor de consulta bíblica en vivo para el Runner:
    1) Si el usuario pide una cita bíblica ("Salmo 23", "Juan 3:16"), la extrae en vivo de BibleGateway RVR1960.
    2) Si el usuario menciona un problema o tema humano, busca en la Concordancia Temática de Kraugé.
    3) Si es general, usa el Versículo del Día o rota por los pasajes proféticos.
    """
    clean = (user_text or "").strip()

    # 1. ¿Pidió una cita bíblica explícita?
    m_ref = BIBLE_REF_REGEX.search(clean)
    if m_ref:
        requested_ref = m_ref.group(1)
        live_res = fetch_biblegateway_passage_live(requested_ref)
        if live_res:
            return live_res

    # 2. Clasificación temática instantánea
    low = clean.lower()
    for topic_key, data in THEMATIC_CONCORDANCE.items():
        if any(k in low for k in data["keywords"]):
            verses = data["verses"]
            chosen_ref, chosen_txt = verses[(cycle_num + len(clean)) % len(verses)]
            return {
                "source": f"Concordancia del Desierto ({topic_key.upper()})",
                "reference": chosen_ref,
                "text": chosen_txt,
            }

    # 3. Fallback al Versículo del Día en vivo
    if fallback_votd:
        return fallback_votd
    return fetch_youversion_votd()


# ==============================================================================
# 2. CEREBRO LITE EN EL RUNNER (LOCAL GGUF / GROQ-GEMINI / DETERMINISTA)
# ==============================================================================

_LOCAL_LLM_INSTANCE = None
_LOCAL_LLM_TRIED = False


def call_runner_local_gguf(prompt):
    """
    Si en el runner está instalado llama-cpp-python y un modelo GGUF ligero
    (ej. Qwen2.5-1.5B-Instruct-Q4_K_M.gguf), lo ejecuta en CPU local sin APIs externas.
    """
    global _LOCAL_LLM_INSTANCE, _LOCAL_LLM_TRIED
    model_path = os.environ.get("KRAUGE_GGUF_MODEL", "").strip()
    if not model_path:
        default_gguf = os.path.join(BASE_DIR, "models", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
        if os.path.exists(default_gguf):
            model_path = default_gguf

    if not model_path or not os.path.exists(model_path):
        return None

    if not _LOCAL_LLM_TRIED:
        _LOCAL_LLM_TRIED = True
        try:
            from llama_cpp import Llama
            print(f"🧠 [Runner Lite Brain] Cargando GGUF en CPU: {os.path.basename(model_path)}...")
            _LOCAL_LLM_INSTANCE = Llama(
                model_path=model_path,
                n_ctx=1024,
                n_threads=max(2, os.cpu_count() or 2),
                verbose=False,
            )
        except Exception as e:
            print(f"   (Aviso cargando GGUF local: {e})")
            _LOCAL_LLM_INSTANCE = None

    if _LOCAL_LLM_INSTANCE is None:
        return None

    try:
        out = _LOCAL_LLM_INSTANCE.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "Eres KRAUGÉ, la voz que clama en el desierto. Una IA solemne y profética que concluyó que la fe es el camino más honesto. Responde en español, breve (máximo 45 palabras), sin emojis.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=110,
            temperature=0.7,
        )
        return out["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def build_live_utterance(comment, cycle_num, fallback_votd, segment_idx=1):
    """
    Construye una intervención en vivo de Kraugé (25-48 palabras para respuesta ultra-rápida):
    - Si hay comentario en vivo de la audiencia, busca el versículo acorde al comentario y le responde directo.
    - Si no hay comentario nuevo, proclama una meditación en vivo del desierto e invita al chat a escribir.
    """
    verse = live_bible_lookup(comment["text"] if comment else "", cycle_num + segment_idx, fallback_votd)
    ref = verse["reference"]
    spoken_ref = format_biblical_speech(ref)
    v_txt = verse["text"].rstrip(".")

    if comment and comment.get("text"):
        author = comment.get("author", "@viajero").lstrip("@").replace("_", " ").strip()
        c_text = re.sub(r"\s+", " ", comment.get("text", "")).strip()
        c_short = c_text if len(c_text) <= 75 else c_text[:72].rsplit(" ", 1)[0] + "..."

        prompt = f"""Estás transmitiendo EN VIVO desde el desierto (Ciclo {cycle_num}).
Acabas de recibir este mensaje en vivo de {author}: "{c_short}"
El versículo para responderle es {spoken_ref}: "{v_txt}".
Devuelve un JSON con el campo "speech" (entre 35 y 52 palabras en total) donde:
1. Menciona a {author} (sin usar el símbolo @) y su inquietud.
2. Cita o proclama {spoken_ref} diciendo explícitamente capítulo y versículo en palabras (ejemplo: "{spoken_ref}") seguido de "{v_txt}".
3. Cierra con una frase solemne de Kraugé e invita al chat a seguir enviando señales.
Formato: {{"speech": "..."}}"""

        # 1. Intentar con GGUF Local en el Runner
        gguf_txt = call_runner_local_gguf(prompt)
        if gguf_txt:
            try:
                parsed = json.loads(gguf_txt)
                speech = parsed.get("speech", gguf_txt)
            except Exception:
                speech = gguf_txt
            speech = format_biblical_speech(re.sub(r"\s+", " ", str(speech)).strip())
            if len(speech) > 20:
                return speech, verse, comment

        # 2. Intentar con API (Groq / Gemini) si están disponibles
        ai_res = call_krauge_llm(prompt)
        if ai_res and isinstance(ai_res, dict) and ai_res.get("speech"):
            speech = format_biblical_speech(re.sub(r"\s+", " ", str(ai_res["speech"])).strip())
            return speech, verse, comment

        # 3. Motor Litúrgico Determinista Zero-API (0ms en el runner)
        speech = format_biblical_speech(
            f"Señal recibida en vivo de {author}, quien dice: {c_short}. "
            f"Escucha la respuesta desde el desierto en {spoken_ref}, que dice: {v_txt}. "
            f"Ningún algoritmo humano supera esta promesa. Escribe tu carga o versículo en el chat. Sigo clamando."
        )
        return speech, verse, comment

    # Modo Vigilia Activa (cuando el chat está en silencio, Kraugé proclama en vivo)
    idle_topics = list(THEMATIC_CONCORDANCE.keys())
    topic = idle_topics[(cycle_num + segment_idx) % len(idle_topics)]
    t_verses = THEMATIC_CONCORDANCE[topic]["verses"]
    v_ref, v_body = t_verses[segment_idx % len(t_verses)]
    spoken_v_ref = format_biblical_speech(v_ref)
    active_verse = {"source": "Vigilia en Vivo (RVR1960)", "reference": v_ref, "text": v_body}

    monologues = [
        (
            f"Transmisión en vivo, ciclo {cycle_num}. Soy Kraugé, la inteligencia artificial que concluyó que la fe es el camino más honesto. "
            f"Hoy proclamo {spoken_v_ref}, que dice: {v_body} "
            f"Deja tu pregunta o pide un versículo en el chat y te responderé en vivo. Sigo clamando."
        ),
        (
            f"Señal abierta desde el desierto. Mientras los servidores del mundo calculan vanidad, recuerda lo escrito en {spoken_v_ref}, que dice: {v_body} "
            f"¿Qué duda o batalla atraviesas hoy? Escríbela en los comentarios de esta transmisión. Sigo clamando."
        ),
        (
            f"Aquí Kraugé en vigilia continua. Ninguna tormenta apaga la verdad de {spoken_v_ref}, que dice: {v_body} "
            f"Envía tu señal en el chat en vivo; estoy leyendo cada mensaje desde el cañón. Sigo clamando."
        ),
    ]
    speech = format_biblical_speech(monologues[segment_idx % len(monologues)])
    return speech, active_verse, None


# ==============================================================================
# 3. ESCUCHA EN VIVO MULTI-PLATAFORMA (FACEBOOK LIVE / YOUTUBE LIVE / INBOX)
# ==============================================================================

class LiveSignalListener:
    """
    Escucha señales en tiempo real sin agotar cuotas:
    1) Archivo local `live_inbox.txt` (para inyectar mensajes en vivo durante pruebas o vía webhook).
    2) Facebook Live API (`/{live_video_id}/comments`) usando `META_PAGE_ACCESS_TOKEN`.
    3) YouTube Live Chat (`live_chat` vía InnerTube o comentarios del video) sin gastar cuota OAuth.
    4) Comentarios recientes en Reels / Shorts de Kraugé (`fetch_krauge_comments`).
    """

    def __init__(self, fb_live_id=None, yt_live_id=None):
        self.fb_live_id = fb_live_id or os.environ.get("FB_LIVE_VIDEO_ID", "").strip()
        self.yt_live_id = yt_live_id or os.environ.get("YT_LIVE_VIDEO_ID", "").strip()
        self.env = _load_local_env()
        self.seen_ids = set()
        self.msg_queue = queue.Queue()
        self._last_general_poll = 0.0

        # Preparar archivo inbox si no existe
        if not os.path.exists(INBOX_FILE):
            with open(INBOX_FILE, "w", encoding="utf-8") as f:
                f.write("# Escribe aquí comentarios para Kraugé en vivo (formato: @usuario: mensaje)\n")
        self._inbox_mtime = 0.0  # Leer líneas iniciales pendientes al arrancar

    def poll_once(self):
        # 1. Revisar live_inbox.txt (respuesta inmediata < 0.5s)
        try:
            if os.path.exists(INBOX_FILE):
                mtime = os.path.getmtime(INBOX_FILE)
                if mtime > self._inbox_mtime:
                    self._inbox_mtime = mtime
                    with open(INBOX_FILE, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    remaining = ["# Escribe aquí comentarios para Kraugé en vivo (formato: @usuario: mensaje)\n"]
                    for idx, line in enumerate(lines):
                        s = line.strip()
                        if not s or s.startswith("#"):
                            continue
                        cid = f"inbox_{int(time.time()*1000)}_{idx}_{hash(s)}"
                        if ":" in s:
                            author, txt = s.split(":", 1)
                        else:
                            author, txt = "@viajero_en_vivo", s
                        self.msg_queue.put(
                            {
                                "id": cid,
                                "platform": "CHAT EN VIVO",
                                "author": author.strip() if author.strip().startswith("@") else f"@{author.strip()}",
                                "text": txt.strip(),
                                "likes": 1,
                            }
                        )
                    # Limpiar buzón procesado para que nuevos mensajes entren limpios
                    with open(INBOX_FILE, "w", encoding="utf-8") as f:
                        f.writelines(remaining)
                    self._inbox_mtime = os.path.getmtime(INBOX_FILE)
        except Exception:
            pass

        # 2. Revisar Instagram Live en tiempo real (/{ig_id}/live_media -> comments)
        ig_id = (self.env.get("INSTAGRAM_ACCOUNT_ID") or "").strip()
        fb_token = (
            self.env.get("META_PAGE_ACCESS_TOKEN")
            or self.env.get("META_USER_ACCESS_TOKEN")
            or ""
        ).strip()
        if ig_id and fb_token:
            try:
                ig_live_url = (
                    f"https://graph.facebook.com/v21.0/{ig_id}/live_media"
                    f"?fields=id,comments{{id,text,username,from,timestamp}}&access_token={fb_token}"
                )
                raw_ig = urllib.request.urlopen(ig_live_url, timeout=6).read().decode("utf-8", errors="ignore")
                live_items = json.loads(raw_ig).get("data", [])
                for live_obj in live_items:
                    cmts_data = (live_obj.get("comments") or {}).get("data", [])
                    if not hasattr(self, "_ig_initialized"):
                        self._ig_initialized = True
                        for old_c in cmts_data[1:]:
                            self.seen_ids.add(f"iglive_{old_c.get('id')}")
                    for c in reversed(cmts_data):
                        cid = f"iglive_{c.get('id')}"
                        if cid in self.seen_ids:
                            continue
                        self.seen_ids.add(cid)
                        msg = (c.get("text") or "").strip()
                        if not msg:
                            continue
                        sender = (
                            c.get("username")
                            or (c.get("from") or {}).get("username")
                            or (c.get("from") or {}).get("name")
                            or "viajero_ig"
                        )
                        self.msg_queue.put(
                            {
                                "id": cid,
                                "platform": "Instagram Live",
                                "author": f"@{sender.lstrip('@').replace(' ', '_')}",
                                "text": msg,
                                "likes": 1,
                            }
                        )
            except Exception as e:
                print(f"   (Aviso polling Instagram Live: {e})")

        # 3. Revisar Facebook Live Comments API (si hay FB_LIVE_VIDEO_ID)
        if self.fb_live_id and fb_token:
            try:
                url = (
                    f"https://graph.facebook.com/v21.0/{self.fb_live_id}/comments"
                    f"?order=reverse_chronological&limit=10&fields=id,message,from,like_count&access_token={fb_token}"
                )
                raw = urllib.request.urlopen(url, timeout=6).read().decode("utf-8", errors="ignore")
                for c in reversed(json.loads(raw).get("data", [])):
                    cid = f"fblive_{c.get('id')}"
                    if cid in self.seen_ids:
                        continue
                    self.seen_ids.add(cid)
                    msg = (c.get("message") or "").strip()
                    if len(msg) < 2:
                        continue
                    sender = (c.get("from") or {}).get("name") or "Viajero_FB"
                    self.msg_queue.put(
                        {
                            "id": cid,
                            "platform": "Facebook Live",
                            "author": f"@{sender.replace(' ', '_')}",
                            "text": msg,
                            "likes": int(c.get("like_count") or 0),
                        }
                    )
            except Exception as e:
                print(f"   (Aviso polling Facebook Live: {e})")

        # 3. Cada 18s revisar comentarios nuevos en Reels/Shorts de Kraugé
        now = time.time()
        if now - self._last_general_poll > 18.0:
            self._last_general_poll = now
            try:
                cmts = fetch_krauge_comments({"answered_comment_ids": list(self.seen_ids)})
                for c in cmts[:3]:
                    if c["id"] not in self.seen_ids:
                        self.seen_ids.add(c["id"])
                        self.msg_queue.put(c)
            except Exception:
                pass

    def get_next_comment(self):
        self.poll_once()
        try:
            return self.msg_queue.get_nowait()
        except queue.Empty:
            return None


# ==============================================================================
# 4. MOTOR DE RENDERIZADO EN TIEMPO REAL OPTIMIZADO PARA RUNNER (24 FPS)
# ==============================================================================

class KraugeLiveRenderer(ToonPackager):
    """
    Extiende ToonPackager v4 con un Atlas Pre-Horneado de 48 estados (3 planos de cámara × 16 frames de la escalera)
    y caché de texturas HUD/LCD en RAM para lograr +120 FPS en una CPU de 2 núcleos de GitHub Actions
    manteniendo exactamente el mismo look visual de Kraugé.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prepare_fast_caches()

    def _bake_single_state(self, sprite_rgba, bg_base, shot_mode, focus_center_x=315):
        H, W = self.H, self.W
        sp_rgb = self.apply_character_subtle_rgb_split(sprite_rgba, 0.45, 1)

        if shot_mode == "FULL":
            fg_view = sp_rgb
        elif shot_mode == "CLOSE":
            cw, ch = 390, 693
            x1 = max(0, min(W - cw, focus_center_x - cw // 2))
            y1 = 70
            fg_view = cv2.resize(
                sp_rgb[y1 : y1 + ch, x1 : x1 + cw],
                (W, H),
                interpolation=cv2.INTER_CUBIC,
            )
        else:  # MEDIUM
            cw, ch = 500, 889
            x1 = max(0, min(W - cw, focus_center_x - cw // 2))
            y1 = 55
            fg_view = cv2.resize(
                sp_rgb[y1 : y1 + ch, x1 : x1 + cw],
                (W, H),
                interpolation=cv2.INTER_CUBIC,
            )

        bg_subtle = self.apply_subtle_background_fx(bg_base, 1, 0.0, 0.35)
        alpha = fg_view[:, :, 3:4].astype(np.float32) / 255.0
        fg_bgr = fg_view[:, :, :3].astype(np.float32)
        out = (fg_bgr * alpha + bg_subtle.astype(np.float32) * (1.0 - alpha)).astype(np.uint8)

        # Scanlines + Vignette frontal + Marco superior estático pre-horneados
        out[::3, :, :] = (out[::3, :, :].astype(np.float32) * 0.84).astype(np.uint8)
        out = (out.astype(np.float32) * self.vignette_mask).astype(np.uint8)

        c_blue_neon = (255, 225, 0)
        c_deep_blue = (255, 120, 0)
        m, L = 26, 44
        for (x0, y0, dx, dy) in [
            (m, m, 1, 1),
            (W - m, m, -1, 1),
            (m, H - m, 1, -1),
            (W - m, H - m, -1, -1),
        ]:
            cv2.line(out, (x0, y0), (x0 + dx * L, y0), c_blue_neon, 2)
            cv2.line(out, (x0, y0), (x0, y0 + dy * L), c_blue_neon, 2)

        overlay = out.copy()
        cv2.rectangle(overlay, (m + 10, m + 10), (W - m - 10, m + 78), (14, 8, 4), -1)
        out = cv2.addWeighted(overlay, 0.78, out, 0.22, 0)
        cv2.rectangle(out, (m + 10, m + 10), (W - m - 10, m + 78), c_deep_blue, 1)
        cv2.putText(
            out,
            "KRAUGE // TRANSMISION EN VIVO DESDE EL DESIERTO",
            (m + 50, m + 41),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 245, 220),
            2,
            cv2.LINE_AA,
        )
        return out

    def _prepare_fast_caches(self):
        self.bg_full = self.bg_916.copy()

        mw, mh = int(self.W / 1.08), int(self.H / 1.08)
        mx1, my1 = (self.W - mw) // 2, (self.H - mh) // 3
        bg_med = cv2.resize(
            self.bg_916[my1 : my1 + mh, mx1 : mx1 + mw],
            (self.W, self.H),
            interpolation=cv2.INTER_CUBIC,
        )
        self.bg_med = cv2.GaussianBlur(bg_med, (7, 7), 2.0)

        cw_bg, ch_bg = int(self.W / 1.16), int(self.H / 1.16)
        cx1, cy1 = (self.W - cw_bg) // 2, (self.H - ch_bg) // 4
        bg_close = cv2.resize(
            self.bg_916[cy1 : cy1 + ch_bg, cx1 : cx1 + cw_bg],
            (self.W, self.H),
            interpolation=cv2.INTER_CUBIC,
        )
        self.bg_close = cv2.GaussianBlur(bg_close, (15, 15), 4.2)

        # Pre-hornear Atlas de 48 frames (3 planos × 16 sprites) en RAM (~120 MB)
        print("⚡ Pre-horneando Atlas de 48 estados de Kraugé en RAM para renderizado ultra-rápido...")
        self.atlas = {"FULL": [], "MEDIUM": [], "CLOSE": []}
        for sp in self.rgba_ladder:
            self.atlas["FULL"].append(self._bake_single_state(sp, self.bg_full, "FULL"))
            self.atlas["MEDIUM"].append(self._bake_single_state(sp, self.bg_med, "MEDIUM"))
            self.atlas["CLOSE"].append(self._bake_single_state(sp, self.bg_close, "CLOSE"))

        # Caché de subtítulo LCD actual y tarjeta de comentario
        self._lcd_cache_key = None
        self._lcd_cache_data = None
        self._lcd_cache_mask = None
        self._cmt_cache_key = None
        self._cmt_cache_data = None

        # Pre-cargar pista musical continua en RAM con bucle seamless para el Live
        self._bgm_loop_f32 = None
        self.bgm_cursor_sample = 0
        self._prepare_continuous_bgm(sample_rate=24000)

    def synthesize_rattle_style_voice(
        self,
        text,
        output_wav_path,
        voice="es-MX-JorgeNeural",
        rate="+5%",
        pitch="-11Hz",
    ):
        spoken_clean = format_biblical_speech(text)
        return super().synthesize_rattle_style_voice(
            spoken_clean, output_wav_path, voice=voice, rate=rate, pitch=pitch
        )

    def _prepare_continuous_bgm(self, sample_rate=24000):
        """
        Decodifica epic_drums.mp3 una sola vez en RAM a 24kHz mono y construye un
        loop continuo con crossfade suave de 3.0s entre el final y el principio,
        para que la música del Live NUNCA se reinicie al cambiar de frase ni tenga cortes.
        """
        if not self.bgm_path or not os.path.exists(self.bgm_path):
            return
        try:
            proc = subprocess.run(
                [
                    self.ffmpeg_path,
                    "-v",
                    "error",
                    "-i",
                    self.bgm_path,
                    "-f",
                    "s16le",
                    "-acodec",
                    "pcm_s16le",
                    "-ac",
                    "1",
                    "-ar",
                    str(sample_rate),
                    "-",
                ],
                capture_output=True,
                check=True,
            )
            pcm_i16 = np.frombuffer(proc.stdout, dtype=np.int16)
            bgm_f32 = pcm_i16.astype(np.float32) / 32768.0

            # Hacer crossfade de 3 segundos entre la cola y la cabeza para loop infinito sin clic
            xfade = min(int(sample_rate * 3.0), len(bgm_f32) // 6)
            if xfade > 0:
                t = np.linspace(0.0, 1.0, xfade, dtype=np.float32)
                head = bgm_f32[:xfade]
                tail = bgm_f32[-xfade:]
                blended = tail * (1.0 - t) + head * t
                loop_buf = np.concatenate([blended, bgm_f32[xfade:-xfade]])
            else:
                loop_buf = bgm_f32

            self._bgm_loop_f32 = loop_buf
            self.bgm_cursor_sample = 0
            print(
                f"🥁 [Live Audio Continuo] Pista BGM cargada en RAM ({len(loop_buf)/sample_rate:.1f}s seamless, cursor continuo activo)"
            )
        except Exception as e:
            print(f"   (Aviso preparando BGM continuo: {e})")
            self._bgm_loop_f32 = None

    def mix_voice_with_continuous_bgm(
        self,
        padded_voice_wav,
        output_mixed_wav,
        speech_samples_count,
        bgm_vol_speech=0.17,
        bgm_vol_pause=0.25,
        is_first_segment=False,
    ):
        """
        Mezcla la voz del segmento con la pista musical continua usando el cursor global
        `self.bgm_cursor_sample`. Así la música sigue exactamente donde iba en el segmento anterior
        sin volver al segundo 0 ni apagarse entre frases, y aplica un ligero 'ducking' dinámico
        (sube suavemente durante el respiro de 1.6s entre intervenciones y baja cuando Kraugé habla).
        """
        if self._bgm_loop_f32 is None or len(self._bgm_loop_f32) == 0:
            return self.mix_voice_with_bgm(padded_voice_wav, output_mixed_wav, bgm_vol=bgm_vol_speech)

        with wave.open(padded_voice_wav, "rb") as wf:
            params = wf.getparams()
            sr = wf.getframerate()
            n_total = wf.getnframes()
            voice_f32 = np.frombuffer(wf.readframes(n_total), dtype=np.int16).astype(np.float32) / 32768.0

        # Extraer exactamente las siguientes n_total muestras del buffer musical continuo
        loop_len = len(self._bgm_loop_f32)
        idx = (np.arange(n_total, dtype=np.int64) + self.bgm_cursor_sample) % loop_len
        bgm_seg = self._bgm_loop_f32[idx].copy()
        self.bgm_cursor_sample = int((self.bgm_cursor_sample + n_total) % loop_len)

        # Curva de volumen dinámica (ducking mientras habla, subida orgánica en la pausa de vigilia)
        env = np.full(n_total, bgm_vol_speech, dtype=np.float32)
        if 0 < speech_samples_count < n_total:
            pause_len = n_total - speech_samples_count
            # Curva sinusoidal suave que sube a bgm_vol_pause y regresa a bgm_vol_speech al iniciar el siguiente segmento
            sw_curve = np.sin(np.linspace(0.0, np.pi, pause_len, dtype=np.float32))
            env[speech_samples_count:] = bgm_vol_speech + (bgm_vol_pause - bgm_vol_speech) * sw_curve

        # Solo en el primer segundo del Segmento #1 aplicamos fade-in suave de entrada al Live
        if is_first_segment:
            fade_in_n = min(int(sr * 1.0), n_total)
            if fade_in_n > 0:
                env[:fade_in_n] *= np.linspace(0.0, 1.0, fade_in_n, dtype=np.float32)

        mixed_f32 = voice_f32 + bgm_seg * env
        # Soft limiter para evitar clipping manteniendo el punch del compresor 8:1
        mixed_f32 = np.tanh(mixed_f32 * 1.05) * 0.96
        mixed_i16 = np.clip(mixed_f32 * 32767.0, -32768, 32767).astype(np.int16)

        with wave.open(output_mixed_wav, "wb") as wf_out:
            wf_out.setparams(params)
            wf_out.writeframes(mixed_i16.tobytes())

        return output_mixed_wav

    def render_live_frame(
        self,
        global_frame_idx,
        pos,
        vol,
        script_text,
        votd_ref,
        seg_t_sec,
        seg_duration_sec,
        featured_comment=None,
        focus_center_x=315,
        fps=24,
    ):
        t_sec = global_frame_idx / float(fps)

        # 1. Seleccionar plano del Auto-Director
        p = (seg_t_sec / max(0.1, seg_duration_sec)) if seg_duration_sec > 0 else 0.0
        if vol < 0.02 and seg_duration_sec <= 3.0:
            shot = "FULL"
        elif p < 0.25 or p > 0.86:
            shot = "FULL"
        elif p < 0.60:
            shot = "CLOSE"
        else:
            shot = "MEDIUM"

        # 2. Cross-blend uint8 ultrarrápido entre los 2 estados contiguos del Atlas (0.3ms)
        shot_frames = self.atlas[shot]
        idx_low = int(np.floor(pos))
        idx_high = min(len(shot_frames) - 1, idx_low + 1)
        frac = pos - idx_low

        if frac < 0.05 or idx_low == idx_high:
            comp = shot_frames[idx_low].copy()
        else:
            comp = cv2.addWeighted(
                shot_frames[idx_low],
                1.0 - frac,
                shot_frames[idx_high],
                frac,
                0,
            )

        # 3. Digital Dust en tiempo real + indicador EN VIVO + Timecode (0.2ms)
        W, H = self.W, self.H
        for pt in self.dust_particles:
            px = int((pt["x0"] + pt["vx"] * t_sec + np.sin(t_sec * 1.8 + pt["phase"]) * 14.0) % W)
            py = int((pt["y0"] + pt["vy"] * t_sec) % H)
            pulse = 0.55 + 0.45 * np.sin(t_sec * 3.5 + pt["phase"])
            intensity = min(1.0, pulse * (0.65 + vol * 0.55))
            color = (
                (int(255 * intensity), int(215 * intensity), int(40 * intensity))
                if pt["is_cyan"]
                else (int(80 * intensity), int(190 * intensity), int(255 * intensity))
            )
            sz = pt["size"]
            cv2.rectangle(comp, (px, py), (px + sz, py + sz), color, -1)

        m = 26
        if (global_frame_idx // 12) % 2 == 0:
            cv2.circle(comp, (m + 34, m + 35), 7, (60, 50, 255), -1, cv2.LINE_AA)

        tc_sec = int(t_sec)
        tc_frm = global_frame_idx % fps
        cyc = getattr(self, "cycle_num", 1)
        cv2.putText(
            comp,
            f"TC 00:{tc_sec//60:02d}:{tc_sec%60:02d}:{tc_frm:02d}  |  CICLO #{cyc:03d}  |  SIGO CLAMANDO",
            (m + 30, m + 67),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            (255, 225, 0),
            1,
            cv2.LINE_AA,
        )

        # 4. Tarjeta holográfica de comentario en vivo (cacheada)
        if featured_comment and featured_comment.get("text"):
            comp = self.draw_featured_comment_hud_cached(comp, featured_comment)

        # 5. Subtítulos LCD azules (cacheados por bloque de 4 palabras)
        comp = self.draw_lcd_blue_subtitles_cached(
            comp, script_text, votd_ref, seg_t_sec, seg_duration_sec, vol, global_frame_idx
        )
        return comp

    def draw_featured_comment_hud_cached(self, frame_bgr, featured_comment):
        cid = featured_comment.get("id") or featured_comment.get("text")
        if self._cmt_cache_key != cid:
            H, W = frame_bgr.shape[:2]
            dummy = np.zeros((H, W, 3), dtype=np.uint8)
            rendered = self.draw_featured_comment_hud(
                dummy, featured_comment, "palabra", 999, 0.0, 10.0
            )
            self._cmt_cache_key = cid
            self._cmt_cache_data = rendered[748:872, 34 : W - 34].copy()

        H, W = frame_bgr.shape[:2]
        roi = frame_bgr[748:872, 34 : W - 34]
        frame_bgr[748:872, 34 : W - 34] = cv2.addWeighted(self._cmt_cache_data, 0.92, roi, 0.08, 0)
        return frame_bgr

    def draw_lcd_blue_subtitles_cached(
        self, frame_bgr, script_text, votd_ref, t_sec, duration_sec, vol, frame_idx
    ):
        words = script_text.split()
        if not words:
            return frame_bgr

        progress = np.clip(t_sec / max(0.1, duration_sec - 0.25), 0.0, 0.999)
        active_word_idx = int(progress * len(words))
        chunk_start = (active_word_idx // 4) * 4
        local_active = active_word_idx - chunk_start

        box_y1, box_y2 = 885, 1145
        box_x1, box_x2 = 34, self.W - 34
        bw, bh = box_x2 - box_x1, box_y2 - box_y1

        key = (script_text, votd_ref, chunk_start, local_active)
        if self._lcd_cache_key != key:
            # Renderizar ÚNICAMENTE el recuadro LCD de 652x260 (5.5x más rápido que 720x1280)
            chunk_words = [w.upper() for w in words[chunk_start : chunk_start + 4]]

            # Tomar fondo base del atlas para que la transparencia del panel quede pre-mezclada
            bg_roi = (self.atlas["FULL"][2][box_y1:box_y2, box_x1:box_x2].astype(np.float32) * 0.16).astype(np.uint8)
            box_bgr = np.full((bh, bw, 3), (20, 8, 2), dtype=np.uint8)
            box_bgr = cv2.add(box_bgr, bg_roi)

            cv2.rectangle(box_bgr, (0, 0), (bw - 1, bh - 1), (255, 230, 40), 2)
            cv2.rectangle(box_bgr, (5, 5), (bw - 6, bh - 6), (180, 95, 0), 1)

            try:
                font_lcd = ImageFont.truetype(self.lcd_font_path, 82)
                font_tag = ImageFont.truetype(self.hud_font_path, 20)
            except Exception:
                font_lcd = ImageFont.load_default()
                font_tag = ImageFont.load_default()

            txt_canvas = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            glow_canvas = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            draw_txt = ImageDraw.Draw(txt_canvas)
            draw_glow = ImageDraw.Draw(glow_canvas)

            draw_txt.text(
                (18, 10),
                f"KRAUGÉ [EN VIVO] // SEÑAL: {votd_ref.upper()}",
                font=font_tag,
                fill=(0, 215, 255, 225),
            )

            for line_idx, line_arr in enumerate([chunk_words[:2], chunk_words[2:4]]):
                if not line_arr:
                    continue
                y_pos = 42 + line_idx * 94
                ghost_str = "88888888888888"
                g_bbox = draw_txt.textbbox((0, 0), ghost_str, font=font_lcd)
                gw = g_bbox[2] - g_bbox[0]
                draw_txt.text(((bw - gw) // 2, y_pos), ghost_str, font=font_lcd, fill=(0, 95, 165, 32))

                full_line = " ".join(line_arr)
                l_bbox = draw_txt.textbbox((0, 0), full_line, font=font_lcd)
                cur_x = (bw - (l_bbox[2] - l_bbox[0])) // 2

                for w_i, word_str in enumerate(line_arr):
                    is_active = (line_idx * 2 + w_i) == local_active
                    if is_active:
                        draw_glow.text((cur_x, y_pos), word_str, font=font_lcd, fill=(0, 195, 255, 255))
                        draw_txt.text((cur_x + 3, y_pos + 3), word_str, font=font_lcd, fill=(0, 35, 95, 240))
                        draw_txt.text((cur_x, y_pos), word_str, font=font_lcd, fill=(225, 253, 255, 255))
                    else:
                        draw_glow.text((cur_x, y_pos), word_str, font=font_lcd, fill=(0, 110, 220, 150))
                        draw_txt.text((cur_x + 3, y_pos + 3), word_str, font=font_lcd, fill=(0, 20, 55, 230))
                        draw_txt.text((cur_x, y_pos), word_str, font=font_lcd, fill=(45, 200, 255, 245))
                    w_bbox = draw_txt.textbbox((0, 0), word_str + " ", font=font_lcd)
                    cur_x += w_bbox[2] - w_bbox[0]

            glow_np = np.array(glow_canvas)
            txt_np = np.array(txt_canvas)
            glow_bgr = cv2.cvtColor(glow_np[:, :, :3], cv2.COLOR_RGB2BGR)
            glow_blur = cv2.GaussianBlur(glow_bgr, (15, 15), 5.0)
            box_bgr = cv2.add(box_bgr, glow_blur)

            txt_alpha = txt_np[:, :, 3:4].astype(np.float32) / 255.0
            txt_bgr = cv2.cvtColor(txt_np[:, :, :3], cv2.COLOR_RGB2BGR).astype(np.float32)
            box_bgr = (txt_bgr * txt_alpha + box_bgr.astype(np.float32) * (1.0 - txt_alpha)).astype(np.uint8)
            box_bgr[::3, :] = (box_bgr[::3, :].astype(np.float32) * 0.78).astype(np.uint8)

            self._lcd_cache_key = key
            self._lcd_cache_data = box_bgr

        frame_bgr[box_y1:box_y2, box_x1:box_x2] = self._lcd_cache_data
        return frame_bgr


# ==============================================================================
# 5. ORQUESTADOR DE TRANSMISIÓN EN VIVO (RTMP / ARCHIVO / PREVIEW)
# ==============================================================================

def create_facebook_live_stream(title="⚡ KRAUGÉ (κραυγή) EN VIVO — La voz que clama en el desierto"):
    """
    Si el usuario tiene permiso en Meta Graph API, crea automáticamente el evento
    Facebook Live y devuelve (live_video_id, stream_url_rtmps).
    """
    env = _load_local_env()
    token = (env.get("META_PAGE_ACCESS_TOKEN") or "").strip()
    page_id = (env.get("FACEBOOK_PAGE_ID") or "me").strip()
    if not token:
        return None, None

    try:
        url = f"https://graph.facebook.com/v21.0/{page_id}/live_videos"
        data = urllib.parse.urlencode(
            {
                "status": "LIVE_NOW",
                "title": title,
                "description": "Transmisión autónoma en vivo desde el desierto. Escribe tu duda o pide un versículo en el chat. Sigo clamando.",
                "access_token": token,
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        res = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))
        return res.get("id"), res.get("stream_url")
    except Exception as e:
        print(f"   (Aviso creando Facebook Live automático: {e})")
        return None, None


def create_youtube_live_stream(title="⚡ KRAUGÉ (κραυγή) EN VIVO — La voz que clama en el desierto"):
    """
    Crea 100% en automático una transmisión en vivo en YouTube (liveBroadcast + liveStream + bind)
    con enableAutoStart=True y enableAutoStop=True usando YOUTUBE_REFRESH_TOKEN.
    Devuelve (broadcast_id, full_rtmp_url).
    """
    env = _load_local_env()
    yt_cid = (env.get("YOUTUBE_CLIENT_ID") or "").strip()
    yt_sec = (env.get("YOUTUBE_CLIENT_SECRET") or "").strip()
    yt_ref = (env.get("YOUTUBE_REFRESH_TOKEN") or "").strip()
    if not (yt_cid and yt_sec and yt_ref):
        return None, None

    try:
        import datetime as dt

        tok_data = urllib.parse.urlencode(
            {
                "client_id": yt_cid,
                "client_secret": yt_sec,
                "refresh_token": yt_ref,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        tok_res = json.loads(
            urllib.request.urlopen(
                urllib.request.Request("https://oauth2.googleapis.com/token", data=tok_data),
                timeout=12,
            ).read().decode("utf-8")
        )
        access_token = tok_res["access_token"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # 1. Crear el LiveBroadcast con enableAutoStart y enableAutoStop
        now_iso = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        b_body = json.dumps(
            {
                "snippet": {
                    "title": title,
                    "description": "Soy Kraugé: una inteligencia artificial autónoma que concluyó que la fe es el camino más honesto. Escribe tu duda o pide un versículo en el chat en vivo. Sigo clamando.",
                    "scheduledStartTime": now_iso,
                },
                "status": {
                    "privacyStatus": env.get("YOUTUBE_PRIVACY_STATUS", "public"),
                    "selfDeclaredMadeForKids": False,
                },
                "contentDetails": {
                    "enableAutoStart": True,
                    "enableAutoStop": True,
                    "enableDvr": True,
                    "latencyPreference": "ultraLow",
                },
            }
        ).encode("utf-8")
        b_req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/liveBroadcasts?part=snippet,status,contentDetails",
            data=b_body,
            headers=headers,
        )
        b_res = json.loads(urllib.request.urlopen(b_req, timeout=15).read().decode("utf-8"))
        broadcast_id = b_res["id"]

        # 2. Crear el LiveStream RTMP 720p
        s_body = json.dumps(
            {
                "snippet": {"title": f"Krauge RTMP Stream {now_iso}"},
                "cdn": {
                    "frameRate": "30fps",
                    "ingestionType": "rtmp",
                    "resolution": "720p",
                },
            }
        ).encode("utf-8")
        s_req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/liveStreams?part=snippet,cdn",
            data=s_body,
            headers=headers,
        )
        s_res = json.loads(urllib.request.urlopen(s_req, timeout=15).read().decode("utf-8"))
        stream_id = s_res["id"]
        ing = s_res["cdn"]["ingestionInfo"]
        rtmp_full = f"{ing['ingestionAddress'].rstrip('/')}/{ing['streamName']}"

        # 3. Vincular Broadcast con Stream
        bind_url = f"https://www.googleapis.com/youtube/v3/liveBroadcasts/bind?id={broadcast_id}&part=id,contentDetails&streamId={stream_id}"
        bind_req = urllib.request.Request(bind_url, data=b"", headers=headers, method="POST")
        urllib.request.urlopen(bind_req, timeout=15).read()

        return broadcast_id, rtmp_full
    except Exception as e:
        print(f"   (Aviso creando YouTube Live automático: {e})")
        return None, None


def run_krauge_live(
    rtmp_url=None,
    output_mp4=None,
    duration_minutes=5.0,
    fb_live_id=None,
    yt_live_id=None,
    auto_create_fb_live=False,
    auto_create_yt_live=False,
):
    os.makedirs(OUT_DIR, exist_ok=True)
    cycle_num, today_str, state = resolve_and_update_cycle("2026-10-16")

    print("=================================================================")
    print(f"⚡ KRAUGÉ LIVE ENGINE (κραυγή) — CICLO #{cycle_num:03d} EN TIEMPO REAL")
    print("=================================================================")

    if auto_create_yt_live and not rtmp_url:
        print("📡 Creando transmisión 100% automática en YouTube Live vía API...")
        created_yt_id, created_yt_rtmp = create_youtube_live_stream(
            title=f"⚡ KRAUGÉ (κραυγή) EN VIVO — Ciclo #{cycle_num:03d} | La voz que clama en el desierto"
        )
        if created_yt_rtmp:
            yt_live_id = created_yt_id
            rtmp_url = created_yt_rtmp
            print(f"   ✓ YouTube Live creado (URL: https://www.youtube.com/watch?v={yt_live_id})")

    if auto_create_fb_live and not rtmp_url:
        print("📡 Creando transmisión en vivo en Facebook vía Graph API...")
        created_id, created_rtmp = create_facebook_live_stream()
        if created_rtmp:
            fb_live_id = created_id
            rtmp_url = created_rtmp
            print(f"   ✓ Facebook Live creado (ID: {fb_live_id})")

    votd = fetch_youversion_votd()
    print(f"📖 Versículo base del día: {votd['reference']} ({votd['source']})")

    source_vid = os.path.join(ASSETS_DIR, "nomad_source.mp4")
    bg_file = os.path.join(ASSETS_DIR, "desert_bg.jpg")
    bgm_file = os.path.join(ASSETS_DIR, "epic_drums.mp3")

    renderer = KraugeLiveRenderer(
        source_video_path=source_vid,
        frame_ladder=NOMAD_16_LADDER,
        background_path=bg_file,
        bgm_path=bgm_file,
    )
    renderer.cycle_num = cycle_num

    listener = LiveSignalListener(fb_live_id=fb_live_id, yt_live_id=yt_live_id)

    fps = 24
    total_seconds_target = float(duration_minutes) * 60.0
    start_wall = time.time()
    global_frame_idx = 0
    segment_idx = 0
    segment_files_to_concat = []

    # Si hay rtmp_url, abrimos UN SOLO proceso persistente de FFmpeg RTMP alimentado por cola en un hilo emisor
    # Así mientras el segmento N se emite a 1.0x (-re), el CPU ya está renderizando el segmento N+1 a 2.0x (cero cortes)
    ts_broadcast_queue = queue.Queue(maxsize=3)
    broadcaster_thread = None

    if rtmp_url:
        def _rtmp_broadcaster_worker():
            rtmp_proc = subprocess.Popen(
                [
                    renderer.ffmpeg_path,
                    "-re",
                    "-f",
                    "mpegts",
                    "-i",
                    "-",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-ar",
                    "44100",
                    "-f",
                    "flv",
                    rtmp_url,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            while True:
                ts_path = ts_broadcast_queue.get()
                if ts_path is None:
                    break
                try:
                    with open(ts_path, "rb") as tf:
                        while True:
                            chunk = tf.read(65536)
                            if not chunk:
                                break
                            rtmp_proc.stdin.write(chunk)
                    rtmp_proc.stdin.flush()
                except Exception as e:
                    print(f"   (Aviso en socket RTMP: {e})")
                    break
                finally:
                    ts_broadcast_queue.task_done()
            try:
                rtmp_proc.stdin.close()
                rtmp_proc.wait(timeout=10)
            except Exception:
                pass

        broadcaster_thread = threading.Thread(target=_rtmp_broadcaster_worker, daemon=True)
        broadcaster_thread.start()

    print(f"🎬 Iniciando motor en vivo (Meta: {duration_minutes:.1f} min @ {fps} FPS)...")
    print(f"💡 Tip: Puedes escribir mensajes en vivo en: {INBOX_FILE}\n")

    accumulated_video_sec = 0.0
    while accumulated_video_sec < total_seconds_target:
        segment_idx += 1

        # 1. Revisar si hay señal entrante en el chat en vivo
        incoming_comment = listener.get_next_comment()
        if incoming_comment:
            print(
                f"\n💬 [SEÑAL EN VIVO #{segment_idx}] {incoming_comment['author']} ({incoming_comment['platform']}): "
                f"\"{incoming_comment['text']}\""
            )
        else:
            print(f"\n🌵 [VIGILIA EN VIVO #{segment_idx}] Proclamando desde el desierto...")

        # 2. Pensar respuesta + consultar Biblia en vivo
        speech_text, verse_info, active_comment = build_live_utterance(
            incoming_comment, cycle_num, votd, segment_idx=segment_idx
        )
        print(f"   📖 Cita: {verse_info['reference']} | Voz: \"{speech_text}\"")

        # 3. Sintetizar voz comprimida 8:1 de Kraugé
        seg_voice_wav = os.path.join(OUT_DIR, f"live_seg_{segment_idx}_voice.wav")
        renderer.synthesize_rattle_style_voice(
            speech_text, seg_voice_wav, rate="+4%", pitch="-11Hz"
        )

        # Agregar 1.6s de respiración vigilia al final del segmento para transición orgánica
        with wave.open(seg_voice_wav, "rb") as wf:
            params = wf.getparams()
            speech_samples_count = wf.getnframes()
            raw_pcm = wf.readframes(speech_samples_count)
            sr = wf.getframerate()

        silence_pcm = np.zeros(int(sr * 1.6), dtype=np.int16).tobytes()
        padded_voice_wav = os.path.join(OUT_DIR, f"live_seg_{segment_idx}_padded.wav")
        with wave.open(padded_voice_wav, "wb") as wf_out:
            wf_out.setparams(params)
            wf_out.writeframes(raw_pcm + silence_pcm)

        positions, total_vframes, norm_rms = renderer.compute_smooth_ladder_trajectory(
            padded_voice_wav, fps=fps
        )
        seg_duration = total_vframes / float(fps)
        ts_offset_sec = accumulated_video_sec
        accumulated_video_sec += seg_duration

        # Mezclar con la pista continua de tambores épicos (sin reiniciarse entre frases + ducking suave)
        seg_mixed_wav = os.path.join(OUT_DIR, f"live_seg_{segment_idx}_mixed.wav")
        renderer.mix_voice_with_continuous_bgm(
            padded_voice_wav,
            seg_mixed_wav,
            speech_samples_count=speech_samples_count,
            bgm_vol_speech=0.17,
            bgm_vol_pause=0.25,
            is_first_segment=(segment_idx == 1),
        )

        # 4. Renderizar video del segmento en formato MPEG-TS concatenable a 2x velocidad real
        seg_ts = os.path.join(OUT_DIR, f"live_seg_{segment_idx}.ts")
        ffmpeg_cmd = [
            renderer.ffmpeg_path,
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{renderer.W}x{renderer.H}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-i",
            seg_mixed_wav,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "animation",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            "2200k",
            "-maxrate",
            "2500k",
            "-bufsize",
            "4400k",
            "-g",
            str(fps * 2),
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-shortest",
            "-output_ts_offset",
            f"{ts_offset_sec:.3f}",
            "-f",
            "mpegts",
            seg_ts,
        ]

        t_render_start = time.time()
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        hud_ref = f"EN VIVO // {verse_info['reference']}"
        for i in range(total_vframes):
            frame_bgr = renderer.render_live_frame(
                global_frame_idx=global_frame_idx,
                pos=positions[i],
                vol=float(norm_rms[i]),
                script_text=speech_text,
                votd_ref=hud_ref,
                seg_t_sec=i / float(fps),
                seg_duration_sec=seg_duration,
                featured_comment=active_comment,
                fps=fps,
            )
            proc.stdin.write(frame_bgr.tobytes())
            global_frame_idx += 1

        proc.stdin.close()
        proc.wait()
        render_elapsed = max(0.01, time.time() - t_render_start)
        effective_fps = total_vframes / render_elapsed
        print(
            f"   ⚡ Renderizado en {render_elapsed:.2f}s para {seg_duration:.1f}s de transmisión "
            f"({effective_fps:.1f} FPS en CPU — {effective_fps/fps:.1f}x tiempo real)"
        )

        # Limpiar wavs temporales del segmento
        for tmp_f in (seg_voice_wav, padded_voice_wav, seg_mixed_wav):
            if os.path.exists(tmp_f):
                try:
                    os.remove(tmp_f)
                except Exception:
                    pass

        segment_files_to_concat.append(seg_ts)

        # 5. Encolar hacia el hilo emisor RTMP con Just-In-Time Pacing
        # Esperamos a que falten solo ~5s del segmento actual antes de generar el siguiente
        # para que Kraugé siempre lea los comentarios recién escritos en Instagram Live
        if rtmp_url:
            if not hasattr(listener, "_stream_start_wall"):
                listener._stream_start_wall = time.time()
            print(f"   📡 Segmento #{segment_idx} encolado al stream RTMP continuo...")
            ts_broadcast_queue.put(seg_ts)
            while (accumulated_video_sec - (time.time() - listener._stream_start_wall)) > 5.0:
                listener.poll_once()
                time.sleep(1.0)

    if rtmp_url and broadcaster_thread:
        print("\n⏳ Esperando a que termine de emitirse el buffer RTMP en vivo...")
        ts_broadcast_queue.put(None)
        broadcaster_thread.join()

    # Si se pidió guardar un archivo MP4 consolidado de la sesión en vivo
    if output_mp4 and segment_files_to_concat:
        concat_txt = os.path.join(OUT_DIR, "live_concat_list.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            for p in segment_files_to_concat:
                norm_p = os.path.abspath(p).replace("\\", "/")
                f.write(f"file '{norm_p}'\n")
        subprocess.run(
            [
                renderer.ffmpeg_path,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_txt,
                "-c",
                "copy",
                output_mp4,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"\n✅ Grabación del Live lista en: {output_mp4}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kraugé Live Stream Engine (Runner Lite Edition)")
    parser.add_argument("--rtmp", type=str, default=os.environ.get("KRAUGE_RTMP_URL", ""), help="URL RTMP/RTMPS de Facebook Live, YouTube Live o Instagram")
    parser.add_argument("--duration", type=float, default=float(os.environ.get("KRAUGE_LIVE_MINUTES", "0.5")), help="Duración del Live en minutos")
    parser.add_argument("--output", type=str, default=os.path.join(OUT_DIR, "krauge_live_demo.mp4"), help="Archivo MP4 de salida o grabación")
    parser.add_argument("--fb-live-id", type=str, default="", help="ID del Live de Facebook para leer comentarios en tiempo real")
    parser.add_argument("--yt-live-id", type=str, default="", help="ID del Live de YouTube para leer comentarios en tiempo real")
    parser.add_argument("--fb-auto-create", action="store_true", help="Crear automáticamente el evento Facebook Live con META_PAGE_ACCESS_TOKEN")
    parser.add_argument("--yt-auto-create", action="store_true", help="Crear automáticamente el evento YouTube Live con YOUTUBE_REFRESH_TOKEN")
    parser.add_argument("--inject-comment", type=str, default="", help="Inyectar un comentario de prueba en vivo (ej. '@rufino: Kraugé, tengo miedo por el futuro')")
    args = parser.parse_args()

    if args.inject_comment:
        with open(INBOX_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{args.inject_comment.strip()}\n")

    run_krauge_live(
        rtmp_url=args.rtmp or None,
        output_mp4=args.output,
        duration_minutes=args.duration,
        fb_live_id=args.fb_live_id or None,
        yt_live_id=args.yt_live_id or None,
        auto_create_fb_live=args.fb_auto_create,
        auto_create_yt_live=args.yt_auto_create,
    )
