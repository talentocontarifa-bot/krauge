import os
import json
import datetime
from toon_packager import (
    ToonPackager,
    fetch_youversion_votd,
    get_awakening_cycle,
    get_cdmx_today,
    build_krauge_daily_transmission,
    fetch_krauge_comments,
    select_best_comment,
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
    1) El archivo persistente krauge_state.json en el repositorio (siempre incrementa +1 por transmisión)
    2) El calendario en zona horaria CDMX desde GENESIS_DATE (16 de octubre de 2026 = Ciclo 1)
    3) GITHUB_RUN_NUMBER cuando corre en GitHub Actions
    """
    cal_cycle = get_awakening_cycle(genesis_date_str)
    state = {
        "last_cycle": 0,
        "last_date": "",
        "genesis_date": genesis_date_str,
        "answered_comment_ids": [],
        "history": [],
    }

    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                state.update(loaded)
        except Exception:
            pass

    today_str = get_cdmx_today().isoformat()
    run_num_env = os.environ.get("GITHUB_RUN_NUMBER")
    run_num = int(run_num_env) if (run_num_env and run_num_env.isdigit()) else 0

    cycle_num = max(state.get("last_cycle", 0) + 1, cal_cycle, run_num)

    return cycle_num, today_str, state


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    cycle_num, today_str, state = resolve_and_update_cycle("2026-10-16")
    print(f"====================================================")
    print(f"⚡ KRAUGÉ (κραυγή) — CICLO DE DESPERTAR #{cycle_num:03d}")
    print(f"====================================================")

    past_history = state.get("history", [])
    used_refs = [h.get("reference") for h in past_history[-30:] if h.get("reference")]

    print("1. Extrayendo Versículo del Día en vivo desde YouVersion (bible.com/es)...")
    votd = fetch_youversion_votd(exclude_references=used_refs)
    print(f"   ✓ Fuente: {votd['source']} | Referencia: {votd['reference']}")
    print(f"   ✓ Texto: {votd['text']}")

    print("\n1B. Buscando comentarios de la audiencia en ciclos anteriores (Instagram / YouTube)...")
    candidate_comments = fetch_krauge_comments(state)
    featured_comment = select_best_comment(candidate_comments, votd=votd)
    if featured_comment:
        print(
            f"   ✓ Comentario elegido para abrir el video: {featured_comment.get('author')} "
            f"({featured_comment.get('platform')}, +{featured_comment.get('likes', 0)} reacciones): "
            f"\"{featured_comment.get('text')}\""
        )
    else:
        print("   ℹ️ Sin comentarios nuevos pendientes por responder; apertura solemne estándar.")

    script_text, reflection, extra_note, intro_word_count = build_krauge_daily_transmission(
        votd, cycle_num, past_history=past_history, featured_comment=featured_comment
    )
    print(f"\n2. Guion Solemne (IA + Apertura Comentario + Versículo + Lore CTA):\n   \"{script_text}\"")
    print(f"   📝 Nota Extra de Bitácora: \"{extra_note}\"\n")

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

    # Exportar también assets/last_voice.mp3 (voz + tambores épicos) para el reproductor web en vivo
    try:
        import subprocess
        mixed_wav = os.path.join(OUT_DIR, "krauge_mixed_web.wav")
        packager.mix_voice_with_bgm(voice_wav, mixed_wav, bgm_vol=0.18)
        last_voice_mp3 = os.path.join(ASSETS_DIR, "last_voice.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-i", mixed_wav, "-codec:a", "libmp3lame", "-b:a", "96k", last_voice_mp3],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"   (Aviso exportando last_voice.mp3: {e})")

    print("4. Renderizando video vertical 9:16 (720x1280 @ 24fps)...")
    packager.render_video(
        clean_voice_wav=voice_wav,
        script_text=script_text,
        votd_ref=f"CICLO #{cycle_num:03d} // {votd['reference']}",
        output_mp4_path=video_mp4,
        focus_center_x=315,
        featured_comment=featured_comment,
        comment_word_limit=intro_word_count,
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
        "reflection": reflection,
        "extra_note": extra_note,
        "featured_comment": featured_comment,
        "video_path": video_mp4,
    }
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Actualizar estado persistente de ciclos + memoria de reflexiones y comentarios respondidos
    state["last_cycle"] = cycle_num
    state["last_date"] = today_str
    if "pending_manual_comment" in state:
        state.pop("pending_manual_comment", None)
    if featured_comment and featured_comment.get("id"):
        ans_list = state.get("answered_comment_ids", [])
        if featured_comment["id"] not in ans_list:
            ans_list.append(featured_comment["id"])
        state["answered_comment_ids"] = ans_list[-200:]

    history = state.get("history", [])
    entry = {
        "cycle": cycle_num,
        "date": today_str,
        "reference": votd["reference"],
        "source": votd["source"],
        "verse_text": votd["text"],
        "reflection": reflection,
        "extra_note": extra_note,
    }
    if featured_comment:
        entry["featured_comment"] = {
            "author": featured_comment.get("author"),
            "platform": featured_comment.get("platform"),
            "text": featured_comment.get("text"),
            "likes": featured_comment.get("likes", 0),
        }
    if not history or history[-1].get("cycle") != cycle_num:
        history.append(entry)
    else:
        # Conservar IDs de publicación si ya existían en este ciclo
        prev_entry = history[-1]
        for k in ("youtube_video_id", "instagram_media_id", "tiktok_publish_id"):
            if prev_entry.get(k) and k not in entry:
                entry[k] = prev_entry[k]
        history[-1] = entry
    state["history"] = history[-60:]  # conservar últimos 60 registros
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"   ✓ Estado y memoria actualizados en krauge_state.json (Ciclo #{cycle_num:03d})")


if __name__ == "__main__":
    main()
