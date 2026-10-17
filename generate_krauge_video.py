import os
import json
import datetime
from toon_packager import (
    ToonPackager,
    fetch_youversion_votd,
    get_awakening_cycle,
    build_krauge_daily_transmission,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUT_DIR = os.path.join(BASE_DIR, "out")
STATE_PATH = os.path.join(BASE_DIR, "krauge_state.json")
DATA_PATH = os.path.join(BASE_DIR, "krauge_data.json")

NOMAD_16_LADDER = [18, 17, 20, 22, 23, 24, 26, 28, 30, 33, 36, 40, 44, 48, 51, 54]


def resolve_and_update_cycle(genesis_date_str="2026-10-16"):
    """
    Determina el ciclo real de despertar de Kraugé combinando:
    1) El calendario desde GENESIS_DATE (16 de octubre de 2026 = Ciclo 1)
    2) El archivo persistente krauge_state.json en el repositorio
    3) GITHUB_RUN_NUMBER cuando corre en GitHub Actions
    """
    cal_cycle = get_awakening_cycle(genesis_date_str)
    state = {"last_cycle": 0, "last_date": "", "genesis_date": genesis_date_str, "history": []}

    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                state.update(loaded)
        except Exception:
            pass

    today_str = datetime.date.today().isoformat()
    run_num_env = os.environ.get("GITHUB_RUN_NUMBER")
    run_num = int(run_num_env) if (run_num_env and run_num_env.isdigit()) else 0

    if state.get("last_date") == today_str and state.get("last_cycle", 0) > 0:
        cycle_num = max(state["last_cycle"], cal_cycle, run_num)
    else:
        cycle_num = max(state.get("last_cycle", 0) + 1, cal_cycle, run_num)

    return cycle_num, today_str, state


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    cycle_num, today_str, state = resolve_and_update_cycle("2026-10-16")
    print(f"====================================================")
    print(f"⚡ KRAUGÉ (κραυγή) — CICLO DE DESPERTAR #{cycle_num:03d}")
    print(f"====================================================")

    print("1. Extrayendo Versículo del Día en vivo desde YouVersion (bible.com/es)...")
    votd = fetch_youversion_votd()
    print(f"   ✓ Fuente: {votd['source']} | Referencia: {votd['reference']}")
    print(f"   ✓ Texto: {votd['text']}")

    script_text = build_krauge_daily_transmission(votd, cycle_num)
    print(f"\n2. Guion Solemne Autosurtido:\n   \"{script_text}\"\n")

    source_vid = os.path.join(ASSETS_DIR, "nomad_source.mp4")
    bg_file = os.path.join(ASSETS_DIR, "desert_bg.jpg")
    bgm_file = os.path.join(ASSETS_DIR, "epic_drums.mp3")

    packager = ToonPackager(
        source_video_path=source_vid,
        frame_ladder=NOMAD_16_LADDER,
        background_path=bg_file,
        bgm_path=bgm_file,
    )
    packager.cycle_num = cycle_num

    voice_wav = os.path.join(OUT_DIR, "krauge_voice.wav")
    video_mp4 = os.path.join(OUT_DIR, "krauge_video.mp4")

    print("3. Sintetizando voz comprimida de Kraugé (edge-tts + DSP 8:1)...")
    packager.synthesize_rattle_style_voice(script_text, voice_wav, rate="+4%", pitch="-11Hz")

    print("4. Renderizando video vertical 9:16 (720x1280 @ 24fps)...")
    packager.render_video(
        clean_voice_wav=voice_wav,
        script_text=script_text,
        votd_ref=f"CICLO #{cycle_num:03d} // {votd['reference']}",
        output_mp4_path=video_mp4,
        focus_center_x=315,
    )
    print(f"   ✓ Video listo: {video_mp4}")

    # Guardar metadatos para publish_video.js
    metadata = {
        "cycle": cycle_num,
        "date": today_str,
        "source": votd["source"],
        "reference": votd["reference"],
        "verse_text": votd["text"],
        "script": script_text,
        "video_path": video_mp4,
    }
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Actualizar estado persistente de ciclos
    state["last_cycle"] = cycle_num
    state["last_date"] = today_str
    history = state.get("history", [])
    if not history or history[-1].get("date") != today_str:
        history.append(
            {
                "cycle": cycle_num,
                "date": today_str,
                "reference": votd["reference"],
                "source": votd["source"],
            }
        )
    state["history"] = history[-60:]  # conservar últimos 60 registros
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"   ✓ Estado actualizado en krauge_state.json (Ciclo #{cycle_num:03d})")


if __name__ == "__main__":
    main()
