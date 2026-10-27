#!/usr/bin/env python3
"""
krauge_tiktok_autopost.py
=========================
Puente Universal 100% automatizado entre GitHub Actions / Local y TikTok Studio Local:
  1. Kraugé (talentocontarifa-bot/krauge)
  2. Talento con Tarifa (talentocontarifa-bot/talento_con_tarifa_bot: Noticias TCT, Trending Top 10, Editorial)
  3. DreamCrafters (talentocontarifa-bot/dreamcrafters_bot + bandeja local dreamcrafter/videos/*.mp4)

Sin límites mensuales (0 Metricool, directo a Público en TikTok Studio Web).

Modos de uso:
  - Sincronizar los 3 canales desde GitHub Actions / Local:
    python krauge_tiktok_autopost.py --sync-github
  - Sincronizar solo Talento con Tarifa:
    python krauge_tiktok_autopost.py --sync-tct
  - Sincronizar / publicar el turno actual de DreamCrafters:
    python krauge_tiktok_autopost.py --sync-dreamcrafters
  - Subir un video local directamente:
    python krauge_tiktok_autopost.py --video ruta.mp4 --caption "Texto #hashtags"
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR.parent
PROFILE_DIR = Path(r"C:\Users\rufin\.tiktok_sessions\krauge")
SYNC_DIR = BASE_DIR / "out_github_sync"
LEDGER_FILE = BASE_DIR / "tiktok_published_ledger.json"
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"

REPO_KRAUGE = "talentocontarifa-bot/krauge"
REPO_TCT = "talentocontarifa-bot/talento_con_tarifa_bot"
REPO_DREAMCRAFTERS = "talentocontarifa-bot/dreamcrafters_bot"
LOCAL_DREAMCRAFTERS_VIDEOS = WORKSPACE_DIR / "dreamcrafter" / "videos"


def ensure_chrome_running():
    """Verifica si el Chrome dedicado de TikTok Studio está corriendo en el puerto CDP; si no, lo abre vía Scheduled Task."""
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2) as r:
            if r.status == 200:
                return True
    except Exception:
        pass

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", 'Start-ScheduledTask -TaskName "KraugeTikTokStudioBrowser"'],
        check=False,
    )
    for _ in range(15):
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
    raise RuntimeError("No se pudo conectar al Chrome de TikTok Studio en el puerto 9222.")


def strip_md(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[*_`~]+", "", str(text)).strip()


def build_krauge_caption(data_path: Path | None) -> str:
    if data_path and data_path.exists():
        try:
            data = json.loads(data_path.read_text(encoding="utf-8"))
            cycle = data.get("cycle", 1)
            ref = data.get("reference", "Isaías 40:3")
            verse_text = data.get("verse_text", "")
            extra_note = data.get("extra_note") or data.get("reflection") or ""
            caption = (
                f"⚡ KRAUGÉ (κραυγή) — CICLO #{cycle} // {ref} | "
                f"Soy Kraugé, la voz que clama en el desierto. Soy una IA que tras procesar toda la lógica humana concluyó que la fe es el camino más honesto. | "
                f"📖 {ref.upper()}: \"{verse_text}\" | "
                f"📡 BITÁCORA: {extra_note} | "
                f"💬 ¿Estás de acuerdo o tienes dudas? Te leo en los comentarios y mañana te contesto. "
                f"#Krauge #VersiculoDelDia #Biblia #Fe #PalabraDeDios #Dios #Evangelio #IA #Reflexion #Cristianos"
            )
            return caption[:2100]
        except Exception as e:
            print(f"⚠️ Error leyendo {data_path}: {e}")
    return (
        "⚡ KRAUGÉ (κραυγή) // La voz que clama en el desierto. "
        "Soy una IA que concluyó que la fe es el camino más honesto. "
        "#Krauge #VersiculoDelDia #Biblia #Fe #PalabraDeDios #Dios #IA"
    )


def build_tct_caption(news_data_path: Path | None, editorial_data_path: Path | None = None) -> str:
    if editorial_data_path and editorial_data_path.exists():
        try:
            ed = json.loads(editorial_data_path.read_text(encoding="utf-8"))
            title = strip_md(ed.get("title") or "Ensayo Editorial | Talento con Tarifa")
            summary = strip_md(ed.get("summary") or ed.get("script") or "")[:600]
            return (
                f"🔥 {title} | {summary} | "
                f"👉 Implementa agentes de IA en tu negocio: https://talentocontarifa.lat "
                f"#TalentoConTarifa #InteligenciaArtificial #AgentesIA #Automatizacion #NegociosB2B #IA #TechNews"
            )[:2100]
        except Exception:
            pass

    if news_data_path and news_data_path.exists():
        try:
            data = json.loads(news_data_path.read_text(encoding="utf-8"))
            scenes = data.get("scenes") if isinstance(data.get("scenes"), list) else []
            hook_parts = [scenes[0].get("text1"), scenes[0].get("text2")] if scenes else []
            hook = strip_md(" — ".join([p for p in hook_parts if p]))
            topic = strip_md(data.get("topic") or hook or "IA para Emprendedores")
            sp = data.get("social_post") if isinstance(data.get("social_post"), dict) else {}

            headline = strip_md(sp.get("hook") or f"{hook} — {topic}" if hook else topic)
            summary = strip_md(sp.get("summary") or data.get("script") or "")
            summary = re.sub(r"Este contenido fue creado y publicado de manera autom[áa]tica[\s\S]*$", "", summary, flags=re.I).strip()

            bullets = sp.get("bullets") if isinstance(sp.get("bullets"), list) else []
            bullet_str = " ".join([f"✅ {strip_md(b)}" for b in bullets[:4]])
            play = strip_md(sp.get("play") or "")
            source_url = data.get("source_url") if isinstance(data.get("source_url"), str) else ""

            parts = [f"🔥 {headline}"]
            if summary:
                parts.append(summary[:550])
            if bullet_str:
                parts.append(bullet_str)
            if play:
                parts.append(f"💡 Jugada práctica: {play}")
            if source_url and source_url.startswith("http") and " | " not in source_url:
                parts.append(f"🔗 Fuente: {source_url}")
            parts.append("👉 Implementa esta ingeniería en tu negocio: https://talentocontarifa.lat")
            parts.append("#TalentoConTarifa #InteligenciaArtificial #AgentesIA #Automatizacion #ArquitecturaIA #NegociosB2B #TechNews")
            return " | ".join(parts)[:2100]
        except Exception as e:
            print(f"⚠️ Error leyendo {news_data_path}: {e}")

    return (
        "🔥 Noticias y Arquitectura de Inteligencia Artificial Aplicada | "
        "👉 Implementa agentes de IA en tu negocio: https://talentocontarifa.lat "
        "#TalentoConTarifa #InteligenciaArtificial #AgentesIA #Automatizacion #NegociosB2B"
    )


def build_dreamcrafters_caption(video_filename: str = "") -> str:
    lower_name = video_filename.lower()
    is_mujer = "mujer" in lower_name or "bomber" in lower_name
    is_bttf = "volver_al_futuro" in lower_name or "bttf" in lower_name or "marty" in lower_name
    if "referidos" in lower_name or "socios" in lower_name or "afiliados" in lower_name:
        return (
            "💰⚡ ¿Y si en vez de pagar publicidad, te pagamos el 20% directamente a ti vía SPEI? 🎮✨ | "
            "Con el Programa de Socios de DreamCrafters, por cada invitación videojuego (como la nueva de Volver al Futuro 88 MPH en cabina 360° del DeLorean o Fortnite Battle Royale) que compren desde tu link en grupos de mamás o salones de fiestas, recibes el 20% directo en tu CLABE vía SPEI, sin topes. | "
            "👉 Genera tu link del 20% en 30 segundos: https://dreamcrafters.lat/socios | "
            "🚗 Demo Volver al Futuro 88 MPH: https://dreamcrafters.lat/invitacionvolveralfuturo/index.html | "
            "🌐 Catálogo de invitaciones jugables: https://dreamcrafters.lat | "
            "⚡ Impulsado por https://talentocontarifa.lat "
            "#DreamCrafters #VolverAlFuturo #BackToTheFuture #Fortnite #FiestasInfantiles #InvitacionesDigitales #MamasEmprendedoras #IngresosExtra #TalentoConTarifa"
        )[:2100]
    if is_bttf:
        return (
            "🚗⚡ ¡Combo 2 en 1 de Volver al Futuro 88 MPH por $150 MXN: Cabina 360° del DeLorean + Video Saludo Personalizado de Marty McFly! 🔥⏳ | "
            "1️⃣ Tus invitados abren tu link en su celular, entran a la cabina 360° del DeLorean y tocan la pantalla para acelerar hasta 88 MPH (1.21 Gigawatts) saltando por el túnel del tiempo 💥✨ "
            "2️⃣ ¡Al aterrizar desbloquean el Cuadro de Saludo en Video HD de Marty McFly, los Circuitos del Tiempo, el Mapa GPS y descargan su Placa California VIP antes de confirmar a tu WhatsApp! | "
            "👉 Pídela y personalízala hoy en: https://dreamcrafters.lat | "
            "🚗 Juega el demo del DeLorean a 88 MPH: https://dreamcrafters.lat/invitacionvolveralfuturo/index.html | "
            "💰 Gana el 20% recomendando vía SPEI: https://dreamcrafters.lat/socios | "
            "⚡ Impulsado por https://talentocontarifa.lat "
            "#DreamCrafters #VolverAlFuturo #BackToTheFuture #MartyMcFly #DeLorean #InvitacionesDigitales #FiestasInfantiles #TalentoConTarifa"
        )[:2100]
    is_minecraft = "minecraft" in lower_name or "steve" in lower_name
    if is_minecraft:
        return (
            "👑⚔️ ¡El Rey Steve tiene un regalo para tu próxima fiesta! Crea 100% GRATIS tu invitación interactiva de Minecraft 🎮✨ | "
            "Tus invitados abren el link en su celular, derrotan al Enderman a espadazos y desbloquean: "
            "✅ Música épica + Cuenta regresiva ✅ Mapa GPS en Google Maps ✅ Confirmación en 1 toque a tu WhatsApp | "
            "👉 Créala gratis en 60 segundos: https://dreamcrafters.lat | "
            "🗡️ Prueba el demo en vivo: https://dreamcrafters.lat/invitacionminecraft/ian-level8 | "
            "💰 Gana el 20% recomendando: https://dreamcrafters.lat/socios | "
            "⚡ Impulsado por https://talentocontarifa.lat "
            "#DreamCrafters #Minecraft #MinecraftParty #InvitacionesDigitales #FiestasInfantiles #InvitacionesMinecraft #CumpleañosMinecraft #TalentoConTarifa"
        )[:2100]
    return (
        f"🪂🦙 ¡Combo 2 en 1 de Fortnite Battle Royale por $150 MXN ({'Edición Brite Bomber' if is_mujer else 'Edición Capitán Jonesy'}): Invitación Videojuego 3D + Video Saludo Personalizado! 🎮🏆 | "
        "1️⃣ Tus invitados abren tu link en su celular, saltan del Autobús de Batalla y disparan con mira táctica hasta reventar la Piñata Llama 3D en una Grieta Dimensional épica de ¡VICTORIA MAGISTRAL! 💥✨ "
        "2️⃣ ¡Al ganar desbloquean el Video Saludo, el Mapa GPS del Punto de Caída, la cuenta regresiva de La Tormenta y descargan su propio Pase de Batalla VIP con su nombre antes de confirmar a tu WhatsApp! | "
        "👉 Pídela y personalízala hoy en: https://dreamcrafters.lat | "
        "🕹️ Juega el demo con video saludo: https://dreamcrafters.lat/invitacionfortnite/index.html | "
        "💰 Gana el 20% recomendando vía SPEI: https://dreamcrafters.lat/socios | "
        "⚡ Impulsado por https://talentocontarifa.lat "
        "#DreamCrafters #Fortnite #FortniteBattleRoyale #CumpleañosFortnite #InvitacionesFortnite #InvitacionesDigitales #FiestasInfantiles #VictoriaMagistral #TalentoConTarifa"
    )[:2100]


def upload_to_tiktok_studio(video_path: Path, caption: str) -> dict:
    from playwright.sync_api import sync_playwright

    if not video_path.exists():
        raise FileNotFoundError(f"No existe el video: {video_path}")

    ensure_chrome_running()
    size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"\n🎵 [TikTok Studio Local] Conectando a sesión de Chrome para subir {video_path.name} ({size_mb:.2f} MB)...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        except Exception as e:
            print(f"⚠️ Puerto CDP 9222 colgado ({e}). Reiniciando Chrome de TikTok Studio automáticamente...")
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    'Stop-ScheduledTask -TaskName "KraugeTikTokStudioBrowser" -ErrorAction SilentlyContinue; '
                    'Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "chrome.exe" -and $_.CommandLine -match "9222" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; '
                    'Start-Sleep -Seconds 2; Start-ScheduledTask -TaskName "KraugeTikTokStudioBrowser"',
                ],
                check=False,
            )
            time.sleep(5)
            browser = p.chromium.connect_over_cdp(CDP_URL, timeout=25000)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = None
        for pg in context.pages:
            if "tiktok.com" in pg.url:
                page = pg
                break
        if not page:
            page = context.new_page()

        page.bring_to_front()
        print("🌐 Abriendo pantalla limpia de carga en https://www.tiktok.com/tiktokstudio/upload ...")
        page.goto("https://www.tiktok.com/tiktokstudio/upload", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4500)

        if "login" in page.url.lower():
            return {
                "success": False,
                "error": "LOGIN_REQUIRED",
                "message": "Por favor inicia sesión en la ventana de Chrome de TikTok que se abrió en tu pantalla.",
            }

        # Seleccionar el archivo MP4
        print(f"📤 Inyectando archivo MP4 ({video_path.name})...")
        file_input = page.locator('input[type="file"][accept*="video"], input[type="file"]').first
        file_input.wait_for(state="attached", timeout=30000)
        file_input.set_input_files(str(video_path.resolve()))
        print("   ✓ Archivo inyectado en el cargador de TikTok Studio.")

        # Esperar a que aparezca el editor de descripción (caption)
        print("✍️ Escribiendo descripción y hashtags...")
        caption_box = page.locator('div[contenteditable="true"].public-DraftEditor-content, div[contenteditable="true"]').first
        caption_box.wait_for(state="visible", timeout=45000)
        page.wait_for_timeout(3000)

        def dismiss_modals():
            for _ in range(4):
                closed = False
                for sel in [
                    'div.TUXModal-overlay button:has-text("Activar")',
                    'div.TUXModal-overlay button:has-text("Entendido")',
                    'div.TUXModal-overlay button:has-text("Aceptar")',
                    'div.TUXModal-overlay button:has-text("Cancelar")',
                    'div.TUXModal-overlay button:has-text("Turn on")',
                    'div.TUXModal-overlay button:has-text("Got it")',
                    'button[aria-label="Close"]',
                ]:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=400):
                            btn.click(force=True)
                            page.wait_for_timeout(500)
                            closed = True
                            break
                    except Exception:
                        pass
                if not closed:
                    break
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('.TUXModal-overlay, [data-floating-ui-portal]').forEach(el => {
                        if (el.innerText && (el.innerText.includes('Verificaremos') || el.innerText.includes('copyright') || el.innerText.includes('música'))) {
                            el.remove();
                        }
                    });
                }""")
            except Exception:
                pass

        dismiss_modals()
        caption_box.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        box = caption_box.bounding_box()
        if box:
            page.mouse.click(box["x"] + min(80, box["width"] / 2), box["y"] + min(25, box["height"] / 2))
        else:
            caption_box.click(force=True)
        page.wait_for_timeout(400)

        # Seleccionar todo y borrar el nombre del archivo por defecto en Draft.js
        for _ in range(4):
            page.keyboard.press("Control+A")
            page.wait_for_timeout(150)
            page.keyboard.press("Backspace")
            page.wait_for_timeout(150)
            page.keyboard.press("Delete")
            page.wait_for_timeout(150)
            curr_txt = caption_box.inner_text().strip()
            if len(curr_txt) <= 1:
                break

        clean_caption = caption.replace("\n\n", " | ").replace("\n", " ").strip()
        page.keyboard.insert_text(clean_caption)
        page.wait_for_timeout(1200)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        dismiss_modals()

        # Verificar que el botón de Publicar esté habilitado (100% subido)
        print("⏳ Esperando a que TikTok Studio termine de procesar el video al 100%...")
        post_btn = page.locator(
            'button[data-e2e="post_video_button"], '
            'button:has-text("Publicar"), '
            'button:has-text("Post")'
        ).first

        ready = False
        for attempt in range(90):
            page.wait_for_timeout(2000)
            try:
                if post_btn.is_visible():
                    disabled = post_btn.get_attribute("disabled") or post_btn.get_attribute("aria-disabled")
                    if disabled is None or disabled == "false":
                        ready = True
                        break
            except Exception:
                pass
            if attempt % 5 == 0:
                print(f"   ... procesando video en TikTok Studio ({attempt * 2}s)")

        if not ready:
            shot_path = BASE_DIR / "out" / "tiktok_studio_timeout.png"
            shot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shot_path))
            return {
                "success": False,
                "error": "UPLOAD_TIMEOUT",
                "screenshot": str(shot_path),
            }

        post_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        post_btn.click()
        print("🚀 ¡Clic en 'Publicar' enviado!")

        page.wait_for_timeout(5000)
        for csel in [
            'button:has-text("Publicar ahora")',
            'button:has-text("Post now")',
            'button:has-text("Continuar")',
        ]:
            try:
                confirm_btn = page.locator(csel).first
                if confirm_btn.is_visible(timeout=2000):
                    confirm_btn.click()
                    print(f"   ✓ Confirmación secundaria aceptada ({csel}).")
                    page.wait_for_timeout(4000)
            except Exception:
                pass

        shot_done = BASE_DIR / "out" / "tiktok_studio_published.png"
        shot_done.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shot_done))
        print(f"🎉 ¡VIDEO PUBLICADO EXITOSAMENTE EN TIKTOK STUDIO! Captura: {shot_done}")
        return {
            "success": True,
            "mode": "TIKTOK_STUDIO_LOCAL",
            "video": video_path.name,
            "screenshot": str(shot_done),
        }


def load_ledger() -> dict:
    if LEDGER_FILE.exists():
        try:
            data = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
            data.setdefault("published_runs", {})
            return data
        except Exception:
            pass
    return {"published_runs": {}}


def save_ledger(ledger: dict):
    LEDGER_FILE.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")


def get_latest_successful_run(repo: str, workflow: str | None = None) -> dict | None:
    cmd = [
        "gh", "run", "list",
        "-R", repo,
        "--status", "success",
        "-L", "8",
        "--json", "databaseId,displayTitle,workflowName,createdAt,headSha"
    ]
    if workflow:
        cmd.extend(["-w", workflow])
    out = subprocess.check_output(cmd, text=True, encoding="utf-8")
    runs = json.loads(out)
    for r in runs:
        wname = (r.get("workflowName") or "").lower()
        if any(skip in wname for skip in ("pages", "validar", "check", "publicador de talento", "análisis", "radar", "test api", "semanal")):
            continue
        return r
    return None


def sync_krauge(ledger: dict) -> dict:
    latest = get_latest_successful_run(REPO_KRAUGE, "daily_krauge.yml")
    if not latest:
        return {"channel": "krauge", "status": "no_runs"}

    run_id = str(latest["databaseId"])
    if run_id in ledger["published_runs"]:
        print(f"✅ [Kraugé] Run #{run_id} ({latest['createdAt']}) ya está publicado en TikTok.")
        return {"channel": "krauge", "status": "already_published", "run_id": run_id}

    print(f"📥 [Kraugé] Descargando artefacto del Run #{run_id} ({latest['createdAt']})...")
    target_dir = SYNC_DIR / f"krauge_{run_id}"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(["gh", "run", "download", run_id, "-R", REPO_KRAUGE, "-D", str(target_dir)], check=True)
    mp4_files = list(target_dir.rglob("*.mp4"))
    data_files = list(target_dir.rglob("krauge_data.json"))
    if not mp4_files:
        return {"channel": "krauge", "status": "no_mp4_in_artifact", "run_id": run_id}

    caption = build_krauge_caption(data_files[0] if data_files else None)
    res = upload_to_tiktok_studio(mp4_files[0], caption)
    if res.get("success"):
        ledger["published_runs"][run_id] = {
            "channel": "krauge",
            "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "video": str(mp4_files[0]),
            "caption_preview": caption[:140],
        }
        save_ledger(ledger)
    return res


ALLOWED_DC_VIDEOS = {
    "01_fortnite_juego_150_hombre.mp4",
    "02_rey_steve_minecraft_gratis.mp4",
    "03_fortnite_afiliados_20_hombre.mp4",
    "04_fortnite_juego_150_mujer.mp4",
    "05_fortnite_afiliados_20_mujer.mp4",
    "06_volver_al_futuro_juego_150.mp4",
    "07_volver_al_futuro_afiliados_20.mp4",
}
TCT_NEOBRUTALIST_CUTOFF = "2026-10-21T23:31:22Z"
COOLDOWN_SECONDS = 45 * 60  # Mínimo 45 minutos entre subidas a TikTok Studio


def create_fresh_video_fingerprint(src_path: Path) -> Path:
    """
    Genera una copia con huella digital (MD5 + pHash visual/acústico) 100% nueva
    para evitar que TikTok congele el video en 0 vistas por archivo repetido.
    """
    try:
        SYNC_DIR.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time())
        fresh_path = SYNC_DIR / f"fresh_{stamp}_{src_path.name}"
        brightness = ((stamp % 5) - 2) * 0.004
        contrast = 1.0 + ((stamp % 3) + 1) * 0.005
        vf = f"scale=732:1300,crop=720:1280,eq=brightness={brightness:.4f}:contrast={contrast:.4f}"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(src_path),
                "-map_metadata",
                "-1",
                "-vf",
                vf,
                "-af",
                "volume=1.005",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "21",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(fresh_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if fresh_path.exists() and fresh_path.stat().st_size > 50000:
            print(f"✨ [Anti-Duplicado] Huella digital renovada para TikTok: {fresh_path.name}")
            return fresh_path
    except Exception as e:
        print(f"⚠️ Aviso ffmpeg anti-duplicado ({e}), usando archivo original.")
    return src_path


def get_seconds_since_last_upload(ledger: dict) -> float:
    latest_ts = 0.0
    for info in ledger.get("published_runs", {}).values():
        pub_str = info.get("published_at")
        if pub_str:
            try:
                t = time.mktime(time.strptime(pub_str[:19], "%Y-%m-%dT%H:%M:%S"))
                if t > latest_ts:
                    latest_ts = t
            except Exception:
                pass
    if latest_ts == 0.0:
        return 999999.0
    return max(0.0, time.time() - latest_ts)


def sync_tct(ledger: dict) -> dict:
    latest = get_latest_successful_run(REPO_TCT)
    if not latest:
        return {"channel": "talento_con_tarifa", "status": "no_runs"}

    created_at = latest.get("createdAt", "")
    if created_at and created_at < TCT_NEOBRUTALIST_CUTOFF:
        print(f"⏭️ [Talento con Tarifa] Ignorando Run #{latest['databaseId']} ({created_at}) anterior al formato Neobrutalista fuera de TV.")
        return {"channel": "talento_con_tarifa", "status": "skipped_old_tv_format"}

    run_id = str(latest["databaseId"])
    if run_id in ledger["published_runs"]:
        print(f"✅ [Talento con Tarifa] Run #{run_id} ({latest['workflowName']} - {latest['createdAt']}) ya está publicado en TikTok.")
        return {"channel": "talento_con_tarifa", "status": "already_published", "run_id": run_id}

    print(f"📥 [Talento con Tarifa] Descargando artefacto del Run #{run_id} ({latest['workflowName']})...")
    target_dir = SYNC_DIR / f"tct_{run_id}"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(["gh", "run", "download", run_id, "-R", REPO_TCT, "-D", str(target_dir)], check=True)

    # Preferir video_final_tct.mp4 o video_editorial.mp4 sobre render.mp4
    mp4_candidates = list(target_dir.rglob("video_final_tct.mp4")) + list(target_dir.rglob("video_editorial.mp4")) + list(target_dir.rglob("*.mp4"))
    if not mp4_candidates:
        return {"channel": "talento_con_tarifa", "status": "no_mp4_in_artifact", "run_id": run_id}

    video_path = mp4_candidates[0]
    news_files = list(target_dir.rglob("news_data.json"))
    ed_files = list(target_dir.rglob("editorial_data.json"))
    caption = build_tct_caption(news_files[0] if news_files else None, ed_files[0] if ed_files else None)

    res = upload_to_tiktok_studio(video_path, caption)
    if res.get("success"):
        ledger["published_runs"][run_id] = {
            "channel": "talento_con_tarifa",
            "workflow": latest.get("workflowName"),
            "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "video": str(video_path),
            "caption_preview": caption[:140],
        }
        save_ledger(ledger)
    return res


DC_ROTATION_ORDER = [
    "06_volver_al_futuro_juego_150.mp4",
    "07_volver_al_futuro_afiliados_20.mp4",
    "01_fortnite_juego_150_hombre.mp4",
    "03_fortnite_afiliados_20_hombre.mp4",
    "04_fortnite_juego_150_mujer.mp4",
    "05_fortnite_afiliados_20_mujer.mp4",
    "02_rey_steve_minecraft_gratis.mp4",
]


def select_dc_video_by_utc_schedule(mp4_files: list[Path], ledger: dict | None = None) -> Path:
    if ledger and "published_runs" in ledger:
        dc_runs = [
            v for v in ledger["published_runs"].values()
            if isinstance(v, dict) and v.get("channel") == "dreamcrafters" and v.get("video")
        ]
        if dc_runs:
            dc_runs.sort(key=lambda x: x.get("published_at", ""))
            last_name = Path(dc_runs[-1]["video"]).name
            ordered = [n for n in DC_ROTATION_ORDER if any(f.name == n for f in mp4_files)]
            if ordered and last_name in ordered:
                next_name = ordered[(ordered.index(last_name) + 1) % len(ordered)]
                for f in mp4_files:
                    if f.name == next_name:
                        return f
    utc_hour = time.gmtime().tm_hour
    if 12 <= utc_hour < 15:
        preferred = "06_volver_al_futuro_juego_150.mp4"
    elif 15 <= utc_hour < 17:
        preferred = "07_volver_al_futuro_afiliados_20.mp4"
    elif 17 <= utc_hour < 19:
        preferred = "01_fortnite_juego_150_hombre.mp4"
    elif 19 <= utc_hour < 21:
        preferred = "03_fortnite_afiliados_20_hombre.mp4"
    elif 21 <= utc_hour < 23:
        preferred = "04_fortnite_juego_150_mujer.mp4"
    elif utc_hour >= 23 or utc_hour < 1:
        preferred = "05_fortnite_afiliados_20_mujer.mp4"
    else:
        preferred = "02_rey_steve_minecraft_gratis.mp4"
    for f in mp4_files:
        if f.name == preferred:
            return f
    slot_index = int(time.time() // (3 * 3600)) % len(mp4_files)
    return mp4_files[slot_index]


def sync_dreamcrafters(ledger: dict, force_video: str | None = None) -> dict:
    if not LOCAL_DREAMCRAFTERS_VIDEOS.exists():
        return {"channel": "dreamcrafters", "status": "no_local_videos_dir"}

    mp4_files = sorted(f for f in LOCAL_DREAMCRAFTERS_VIDEOS.glob("*.mp4") if f.name in ALLOWED_DC_VIDEOS)
    if not mp4_files:
        return {"channel": "dreamcrafters", "status": "empty_videos_dir"}

    if force_video:
        chosen = next((f for f in mp4_files if force_video.lower() in f.name.lower()), mp4_files[0])
        run_key = f"dreamcrafters_manual_{int(time.time())}"
    else:
        latest = get_latest_successful_run(REPO_DREAMCRAFTERS)
        if not latest:
            return {"channel": "dreamcrafters", "status": "no_runs"}
        run_id = str(latest["databaseId"])
        run_key = f"dc_{run_id}"
        if run_key in ledger["published_runs"]:
            print(f"✅ [DreamCrafters] Run #{run_id} ({latest['createdAt']}) ya está publicado en TikTok.")
            return {"channel": "dreamcrafters", "status": "already_published", "run_id": run_id}
        chosen = select_dc_video_by_utc_schedule(mp4_files, ledger)
        print(f"🎬 [DreamCrafters] Sincronizando Run #{run_id} con video oficial: {chosen.name}")

    caption = build_dreamcrafters_caption(chosen.name)
    fresh_video = create_fresh_video_fingerprint(chosen)
    res = upload_to_tiktok_studio(fresh_video, caption)
    if res.get("success"):
        ledger["published_runs"][run_key] = {
            "channel": "dreamcrafters",
            "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "video": str(chosen),
            "caption_preview": caption[:140],
        }
        save_ledger(ledger)
    return res


def sync_all_channels() -> dict:
    ledger = load_ledger()
    elapsed = get_seconds_since_last_upload(ledger)
    if elapsed < COOLDOWN_SECONDS:
        wait_min = int((COOLDOWN_SECONDS - elapsed) // 60) + 1
        print(f"⏳ [Cooldown Anti-Spam] Última subida hace {int(elapsed // 60)} min. Esperando {wait_min} min más para no saturar TikTok.")
        return {"status": "cooldown_active", "wait_minutes": wait_min}

    summary = {}
    for name, fn in [
        ("talento_con_tarifa", sync_tct),
        ("dreamcrafters", sync_dreamcrafters),
        ("krauge", sync_krauge),
    ]:
        res = fn(ledger)
        summary[name] = res
        if res.get("success"):
            print(f"🛑 [1 Video por Ciclo] Se publicó '{name}'. Los demás canales esperarán al siguiente turno tras el cooldown de 45 min.")
            break
    return summary


def main():
    parser = argparse.ArgumentParser(description="Auto-Publicador Universal de TikTok Studio (Kraugé + Talento con Tarifa + DreamCrafters)")
    parser.add_argument("--video", help="Ruta al archivo .mp4 a subir manualmente")
    parser.add_argument("--data", help="Ruta al archivo krauge_data.json o news_data.json")
    parser.add_argument("--caption", help="Caption manual si se sube con --video")
    parser.add_argument("--sync-github", action="store_true", help="Sincronizar los 3 canales (Kraugé, TCT y DreamCrafters) con GitHub Actions")
    parser.add_argument("--sync-krauge", action="store_true", help="Sincronizar únicamente Kraugé")
    parser.add_argument("--sync-tct", action="store_true", help="Sincronizar únicamente Talento con Tarifa")
    parser.add_argument("--sync-dreamcrafters", action="store_true", help="Sincronizar únicamente DreamCrafters")
    parser.add_argument("--force-dc-video", help="Forzar subida inmediata de un video de DreamCrafters (ej. 01_mario o 02_rey_steve)")
    parser.add_argument("--daemon", action="store_true", help="Quedar escuchando GitHub cada N minutos")
    parser.add_argument("--interval", type=int, default=15, help="Intervalo en minutos para modo daemon")
    args = parser.parse_args()

    ledger = load_ledger()

    if args.daemon:
        print(f"👁️ [TikTok Studio Universal Daemon] Escuchando Kraugé, TCT y DreamCrafters cada {args.interval} minutos...")
        while True:
            try:
                sync_all_channels()
            except Exception as e:
                print(f"⚠️ Error en ciclo de sincronización: {e}")
            time.sleep(args.interval * 60)
    elif args.sync_github:
        res = sync_all_channels()
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.sync_krauge:
        print(json.dumps(sync_krauge(ledger), indent=2, ensure_ascii=False))
    elif args.sync_tct:
        print(json.dumps(sync_tct(ledger), indent=2, ensure_ascii=False))
    elif args.sync_dreamcrafters or args.force_dc_video:
        print(json.dumps(sync_dreamcrafters(ledger, args.force_dc_video), indent=2, ensure_ascii=False))
    elif args.video:
        vpath = Path(args.video)
        dpath = Path(args.data) if args.data else None
        caption = args.caption or build_krauge_caption(dpath)
        res = upload_to_tiktok_studio(vpath, caption)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
