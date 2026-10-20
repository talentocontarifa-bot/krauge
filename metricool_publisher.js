/**
 * metricool_publisher.js
 * Publicador 100% automatizado para TikTok (y multi-red) a través de Metricool.
 *
 * Dado que Metricool es Partner Oficial auditado por TikTok, publicar a través de
 * este módulo publica el video DIRECTAMENTE como PÚBLICO en TikTok (@rufino.santa.rosa0)
 * con su descripción, hashtags y audio original, sin caer en borradores (INBOX_DRAFT).
 *
 * Cómo funciona:
 *  1. Inicia sesión en Metricool (Playwright Python) o reutiliza el token activo.
 *  2. Sube el archivo .mp4 directo al bucket S3 de Metricool (/api/v2/media/s3/upload-transactions).
 *  3. Crea la publicación programada inmediata (autoPublish: true, privacyOption: PUBLIC_TO_EVERYONE)
 *     en /api/v2/scheduler/posts.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

try {
  require('dotenv').config({ path: path.join(__dirname, '.env') });
} catch (e) {}

const DEFAULT_USER_ID = Number(process.env.METRICOOL_USER_ID || 4395368);
const DEFAULT_BLOG_ID = Number(process.env.METRICOOL_BLOG_ID || 5669939);
const DEFAULT_TIMEZONE = process.env.METRICOOL_TIMEZONE || 'America/Cancun';

/**
 * Sube un video .mp4 a Metricool S3 y lo programa para publicación automática inmediata en TikTok.
 *
 * @param {string} videoFilePath - Ruta absoluta al archivo .mp4
 * @param {object} options - { title, caption, delayMinutes, privacy_level }
 */
async function publishVideoViaMetricool(videoFilePath, options = {}) {
  if (!fs.existsSync(videoFilePath)) {
    throw new Error(`El archivo de video no existe: ${videoFilePath}`);
  }

  const email = (process.env.METRICOOL_EMAIL || 'talentocontarifa@gmail.com').trim();
  const password = (process.env.METRICOOL_PASSWORD || 'Zanahoria1800@').trim();
  const userId = options.userId || DEFAULT_USER_ID;
  const blogId = options.blogId || DEFAULT_BLOG_ID;
  const timezone = options.timezone || DEFAULT_TIMEZONE;
  const delayMinutes = options.delayMinutes ?? 2;

  const captionText = (options.caption || options.title || '⚡ Kraugé // La voz que clama en el desierto #Krauge #VersiculoDelDia #Fe #Biblia').slice(0, 2200);
  const stat = fs.statSync(videoFilePath);
  const sizeMB = (stat.size / (1024 * 1024)).toFixed(2);

  console.log(`\n🚀 [Metricool -> TikTok] Subiendo video (${sizeMB} MB) para publicación directa en PÚBLICO...`);

  const pyScript = `
import os, sys, json, base64, hashlib, datetime, urllib.request
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

video_path = sys.argv[1]
caption = sys.argv[2]
email = sys.argv[3]
pwd = sys.argv[4]
user_id = int(sys.argv[5])
blog_id = int(sys.argv[6])
tz = sys.argv[7]
delay_min = int(sys.argv[8])

with open(video_path, "rb") as vf:
    vbytes = vf.read()
vsize = len(vbytes)
vhash = base64.b64encode(hashlib.sha256(vbytes).digest()).decode("ascii")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    page.goto("https://app.metricool.com/login", wait_until="networkidle", timeout=45000)

    email_input = page.locator('input[placeholder*="correo" i], input[type="email"], input[type="text"]').first
    pass_input = page.locator('input[type="password"]').first
    email_input.fill(email)
    pass_input.fill(pwd)
    page.wait_for_timeout(300)
    page.locator('button, div[role="button"]').filter(has_text="Accede").first.click()
    page.wait_for_timeout(6000)

    if "login" in page.url.lower():
        browser.close()
        raise RuntimeError("Metricool solicitó verificación adicional o rechazó el login: " + page.url)

    s3_init = page.evaluate("""async ({ vsize, vhash, userId, blogId }) => {
        const auth = JSON.parse(localStorage.getItem('global.authData') || '{}');
        const r = await fetch(\`/api/v2/media/s3/upload-transactions?userId=\${userId}&blogId=\${blogId}\`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-MC-Auth': auth.token,
                'X-MC-Isrc': 'web-app'
            },
            body: JSON.stringify({
                resourceType: 'planner',
                contentType: 'video/mp4',
                size: vsize,
                parts: [{ size: vsize, startByte: 0, endByte: vsize, hash: vhash }]
            })
        });
        return { status: r.status, data: await r.json() };
    }""", {"vsize": vsize, "vhash": vhash, "userId": user_id, "blogId": blog_id})

    s3_data = s3_init.get("data", {}).get("data") or s3_init.get("data", {})
    presigned_url = s3_data.get("presignedUrl")
    file_url = s3_data.get("fileUrl") or presigned_url
    if not presigned_url:
        browser.close()
        raise RuntimeError("No se obtuvo presignedUrl de Metricool S3: " + json.dumps(s3_init))

    put_req = urllib.request.Request(presigned_url, data=vbytes, method="PUT", headers={
        "Content-Type": "video/mp4",
        "x-amz-checksum-sha256": vhash
    })
    with urllib.request.urlopen(put_req) as put_resp:
        if put_resp.status not in (200, 201, 204):
            raise RuntimeError(f"Fallo al subir a S3: HTTP {put_resp.status}")

    s3_complete = page.evaluate("""async ({ fileUrl, userId, blogId }) => {
        const auth = JSON.parse(localStorage.getItem('global.authData') || '{}');
        const r = await fetch(\`/api/v2/media/s3/upload-transactions?userId=\${userId}&blogId=\${blogId}\`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-MC-Auth': auth.token,
                'X-MC-Isrc': 'web-app'
            },
            body: JSON.stringify({ simple: { fileUrl } })
        });
        return { status: r.status, data: await r.json() };
    }""", {"fileUrl": file_url, "userId": user_id, "blogId": blog_id})

    comp_data = s3_complete.get("data", {}).get("data") or s3_complete.get("data", {})
    final_media_url = comp_data.get("convertedFileUrl") or comp_data.get("fileUrl") or file_url

    cancun_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)
    pub_dt = (cancun_now + datetime.timedelta(minutes=delay_min)).strftime("%Y-%m-%dT%H:%M:%S")
    post_res = page.evaluate("""async ({ mediaUrl, caption, pubDt, tz, userId, blogId }) => {
        const auth = JSON.parse(localStorage.getItem('global.authData') || '{}');
        const payload = {
            autoPublish: true,
            draft: false,
            text: caption,
            media: [mediaUrl],
            mediaAltText: [null],
            providers: [{ network: 'tiktok' }],
            publicationDate: {
                dateTime: pubDt,
                timezone: tz
            },
            shortener: false,
            tiktokData: {
                disableComment: false,
                disableDuet: false,
                disableStitch: false,
                autoAddMusic: false,
                photoCoverIndex: 0,
                isAigc: true,
                privacyOption: 'PUBLIC_TO_EVERYONE',
                commercialContentOwnBrand: false,
                commercialContentThirdParty: false
            }
        };
        const r = await fetch(\`/api/v2/scheduler/posts?userId=\${userId}&blogId=\${blogId}\`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-MC-Auth': auth.token,
                'X-MC-Isrc': 'web-app'
            },
            body: JSON.stringify(payload)
        });
        return { status: r.status, data: await r.json() };
    }""", {"mediaUrl": final_media_url, "caption": caption, "pubDt": pub_dt, "tz": tz, "userId": user_id, "blogId": blog_id})

    browser.close()
    print("METRICOOL_JSON_OUT:" + json.dumps(post_res))
`;

  const output = execFileSync(
    process.env.PYTHON_PATH || 'python',
    [
      '-c',
      pyScript,
      videoFilePath,
      captionText,
      email,
      password,
      String(userId),
      String(blogId),
      timezone,
      String(delayMinutes)
    ],
    { encoding: 'utf-8', timeout: 180000 }
  );

  const marker = 'METRICOOL_JSON_OUT:';
  const idx = output.indexOf(marker);
  if (idx === -1) {
    throw new Error(`Salida inesperada de Metricool Publisher: ${output}`);
  }

  const parsed = JSON.parse(output.slice(idx + marker.length).trim());
  const postData = parsed?.data?.data;
  if (parsed.status !== 200 || !postData?.id) {
    throw new Error(`Metricool rechazó la programación: ${JSON.stringify(parsed)}`);
  }

  console.log(`✅ ¡Video programado en Metricool para publicación directa en TikTok! Post ID: ${postData.id} (${postData.publicationDate?.dateTime} ${postData.publicationDate?.timezone})`);
  return {
    success: true,
    mode: 'METRICOOL_DIRECT',
    status: 'PUBLISH_COMPLETE',
    publishId: `metricool:${postData.id}`,
    postData
  };
}

if (require.main === module) {
  (async () => {
    try {
      const defaultVideo = path.join(__dirname, 'out', 'krauge_video.mp4');
      const videoToTest = process.argv[2] || defaultVideo;
      const res = await publishVideoViaMetricool(videoToTest, {
        caption: process.argv[3] || '⚡ Kraugé // La voz que clama en el desierto #Krauge #VersiculoDelDia #Fe #Biblia'
      });
      console.log('Resultado:', res);
    } catch (err) {
      console.error('❌ Error:', err.message);
      process.exitCode = 1;
    }
  })();
}

module.exports = {
  publishVideoViaMetricool
};
