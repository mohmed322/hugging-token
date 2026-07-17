"""
322 — مقصّ أفضل 60 ثانية من فيديو يوتيوب (بدون ذكاء اصطناعي)
================================================================
تطبيق Streamlit بتصميم فضائي (خلفية سودا + نجوم متحركة + رائد فضاء وكواكب
بتظهر بين فترة وفترة).

الفكرة:
-------
المستخدم بيحط لينك يوتيوب لفيديو طويل، والتطبيق:
  1) بينزّل الفيديو محليًا (yt-dlp).
  2) بيحلل "طاقة الصوت" (RMS Loudness) على طول الفيديو كله عن طريق تحليل
     إشارة صوتية بحتة (Digital Signal Processing) — من غير أي نموذج ذكاء
     اصطناعي أو تعلم آلي. الفكرة إن اللحظات "الأهم" غالبًا بتكون أعلى صوتًا
     (كلام، حماس، موسيقى، تصفيق...) مقارنة باللحظات الهادئة.
  3) بيدوّر على أفضل نافذة مدتها 60 ثانية (بأعلى متوسط طاقة صوت) باستخدام
     Sliding Window + Prefix Sums (خوارزمية رياضية بسيطة، مفيش أي AI فيها).
  4) بيقص الفيديو عند اللحظة دي بـ ffmpeg ويطلعه جاهز للتحميل.
  5) المستخدم كمان يقدر يعدّل نقطة البداية والمدة يدويًا زي أي video editor
     بسيط، ويقص من غير ما يعتمد على التحليل التلقائي خالص لو حاب.

المتطلبات على السيرفر (مش Python packages بس):
------------------------------------------------
- ffmpeg لازم يكون متثبت على السيرفر (متاح في PATH).
- مكتبة yt-dlp (requirements.txt).
"""

import os
import shutil
import subprocess
import tempfile
import traceback
import wave
import array

import streamlit as st

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# ----------------------------------------------------------------------------
# إعدادات عامة
# ----------------------------------------------------------------------------
CLIP_DURATION = 60          # مدة المقطع النهائي بالثواني
ANALYSIS_WINDOW = 1.0       # حجم "بلاطة" التحليل الصوتي بالثواني
MAX_DOWNLOAD_SECONDS = None  # ممكن تحطها رقم (مثلاً 3600) لو عايز تحدد أقصى مدة فيديو مسموح بيها

st.set_page_config(page_title="322", page_icon="🌌", layout="centered")

# ----------------------------------------------------------------------------
# توليد نمط النجوم (نفس الخلفية الفضائية الأصلية بدون أي تغيير)
# ----------------------------------------------------------------------------
import random


def _star_shadows(count: int, color: str, seed: int) -> str:
    rng = random.Random(seed)
    points = []
    for _ in range(count):
        x = rng.uniform(0, 100)
        y = rng.uniform(0, 100)
        points.append(f"{x:.2f}vw {y:.2f}vh 0 0 {color}")
    return ", ".join(points)


_STARS_DIM = _star_shadows(260, "rgba(255,255,255,0.30)", seed=4)
_STARS_TINY = _star_shadows(420, "rgba(255,255,255,0.55)", seed=1)
_STARS_SMALL = _star_shadows(220, "rgba(255,255,255,0.85)", seed=2)
_STARS_BIG = _star_shadows(90, "rgba(201,191,255,0.95)", seed=3)

_STAR_TILE_HTML = (
    f'<div class="star-layer tw-a" style="width:1px;height:1px;box-shadow:{_STARS_DIM}"></div>'
    f'<div class="star-layer tw-a" style="width:1px;height:1px;box-shadow:{_STARS_TINY}"></div>'
    f'<div class="star-layer tw-b" style="width:2px;height:2px;box-shadow:{_STARS_SMALL}"></div>'
    f'<div class="star-layer tw-c" style="width:3px;height:3px;box-shadow:{_STARS_BIG}"></div>'
)

_SPACE_BACKGROUND_HTML = (
    '<div class="space-bg">'
    '<div class="star-track">'
    f'<div class="star-tile">{_STAR_TILE_HTML}</div>'
    f'<div class="star-tile">{_STAR_TILE_HTML}</div>'
    '</div>'
    '<div class="astronaut">'
    '<svg width="34" height="34" viewBox="0 0 34 34">'
    '<ellipse cx="17" cy="20" rx="8" ry="10" fill="#e5e7eb"/>'
    '<circle cx="17" cy="10" r="8" fill="#f5f5f7"/>'
    '<circle cx="17" cy="10" r="5.5" fill="#7c5cff" opacity="0.55"/>'
    '<rect x="4" y="17" width="6" height="3" rx="1.5" fill="#cbd5e1"/>'
    '<rect x="24" y="17" width="6" height="3" rx="1.5" fill="#cbd5e1"/>'
    '</svg>'
    '</div>'
    '<div class="planet planet-1"></div>'
    '<div class="planet planet-2"></div>'
    '<div class="planet planet-3"></div>'
    '</div>'
)

# ----------------------------------------------------------------------------
# CSS — الثيم الفضائي الكامل (نفس الأصلي)
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none !important; background: transparent !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    .stApp {
        background: #05060a !important;
        overflow-x: hidden;
    }

    .block-container {
        max-width: 720px;
        margin: 0 auto;
        padding-top: 2.5rem !important;
        position: relative;
        z-index: 1;
    }

    h1, h2, h3, p, label, span, div { color: #ffffff; }

    .space-bg {
        position: fixed;
        inset: 0;
        z-index: 0;
        overflow: hidden;
        pointer-events: none;
    }

    .star-track {
        position: absolute;
        top: 0; left: 0;
        width: 200vw;
        height: 100vh;
        display: flex;
        animation: starDrift 40s linear infinite;
    }
    .star-tile {
        position: relative;
        width: 100vw;
        height: 100vh;
        flex: 0 0 100vw;
    }
    .star-layer {
        position: absolute;
        top: 0; left: 0;
        background: transparent;
        border-radius: 50%;
    }
    @keyframes starDrift {
        from { transform: translateX(0); }
        to   { transform: translateX(-100vw); }
    }

    .tw-a { animation: twinkleA 3s ease-in-out infinite alternate; }
    .tw-b { animation: twinkleB 4s ease-in-out infinite alternate; }
    .tw-c {
        animation: twinkleC 2.5s ease-in-out infinite alternate;
        filter: drop-shadow(0 0 3px rgba(201,191,255,0.6));
    }
    @keyframes twinkleA { from { opacity: .25; } to { opacity: .7; } }
    @keyframes twinkleB { from { opacity: .4; }  to { opacity: .9; } }
    @keyframes twinkleC { from { opacity: .55; } to { opacity: 1; } }

    .astronaut {
        position: absolute;
        top: 18%;
        animation: crossFar 17s linear infinite;
    }
    .astronaut svg { animation: tumble 6s ease-in-out infinite alternate; }
    @keyframes tumble { from { transform: rotate(-8deg); } to { transform: rotate(8deg); } }

    .planet { position: absolute; border-radius: 50%; }
    .planet-1 {
        top: 12%; width: 26px; height: 26px; background: #7c5cff;
        box-shadow: inset -6px -5px 0 rgba(0,0,0,.25), 0 0 10px rgba(255,255,255,.15);
        animation: crossFar 19s linear infinite;
        animation-delay: -4s;
    }
    .planet-2 {
        top: 55%; width: 18px; height: 18px; background: #38bdf8;
        box-shadow: inset -4px -3px 0 rgba(0,0,0,.25);
        animation: crossFar 22s linear infinite;
        animation-delay: -11s;
    }
    .planet-3 {
        top: 75%; width: 34px; height: 34px; background: #f472b6;
        box-shadow: inset -8px -6px 0 rgba(0,0,0,.25), 0 0 12px rgba(255,255,255,.12);
        animation: crossFar 20s linear infinite;
        animation-delay: -6s;
    }

    @keyframes crossFar {
        0%   { left: 110%; opacity: 0; }
        55%  { left: 110%; opacity: 0; }
        60%  { opacity: 1; }
        92%  { left: -15%; opacity: 1; }
        100% { left: -15%; opacity: 0; }
    }

    .app-header { text-align: center; margin-bottom: 2rem; }
    .app-logo {
        font-size: 44px;
        font-weight: 800;
        letter-spacing: 2px;
        color: #ffffff;
        text-shadow:
            0 0 10px rgba(255,255,255,0.55),
            0 0 22px rgba(255,255,255,0.30),
            0 0 38px rgba(255,255,255,0.15);
        animation: logoGlow 2.2s ease-in-out infinite alternate;
    }
    @keyframes logoGlow {
        from {
            text-shadow:
                0 0 8px rgba(255,255,255,0.40),
                0 0 16px rgba(255,255,255,0.22),
                0 0 28px rgba(255,255,255,0.10);
        }
        to {
            text-shadow:
                0 0 13px rgba(255,255,255,0.70),
                0 0 26px rgba(255,255,255,0.40),
                0 0 44px rgba(255,255,255,0.20);
        }
    }
    .app-header p {
        color: #e5e7eb !important;
        font-size: 0.95rem;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
        margin-top: 0.3rem;
    }

    div[data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }

    div[data-testid="stTextInput"] input,
    div[class*="stTextInput"] input {
        background: rgba(255,255,255,0.04) !important;
        background-color: rgba(255,255,255,0.04) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        border: 1px solid rgba(255,255,255,0.14) !important;
        box-shadow: none !important;
        border-radius: 22px !important;
        color: #ffffff !important;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
    }
    div[data-testid="stTextInput"] input::placeholder {
        color: rgba(255,255,255,0.55) !important;
    }

    div[data-testid="stSelectbox"] div[data-baseweb="select"],
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] div[role="combobox"],
    div[class*="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div {
        background: rgba(255,255,255,0.04) !important;
        background-color: rgba(255,255,255,0.04) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        border-color: rgba(255,255,255,0.14) !important;
        box-shadow: none !important;
        border-radius: 14px !important;
    }
    div[data-testid="stSelectbox"] *,
    div[data-baseweb="select"] * {
        color: #ffffff !important;
    }

    .stButton button,
    div[data-testid="stForm"] button {
        background: rgba(255,255,255,0.04) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        border: 1px solid rgba(255,255,255,0.14) !important;
        border-radius: 999px !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
        width: 100%;
    }

    .stDownloadButton button {
        background: rgba(255,255,255,0.04) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        border: 1px solid rgba(255,255,255,0.14) !important;
        border-radius: 999px !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        width: 100%;
    }

    div[data-testid="stExpander"] {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 16px !important;
    }

    div[data-testid="stSlider"] {
        padding: 0.5rem 0.2rem 1rem 0.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# الخلفية الفضائية + الشعار
# ----------------------------------------------------------------------------
st.markdown(_SPACE_BACKGROUND_HTML, unsafe_allow_html=True)

st.markdown(
    '<div class="app-header"><div class="app-logo">322</div>'
    '<p>حط لينك يوتيوب — هنحلل الصوت بس (خفيف وسريع) عشان نقترح أقوى 60 '
    'ثانية، وهنحمّل المقطع المختار بس من غير ما ننزّل الفيديو كامل</p></div>',
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# أدوات مساعدة: معاينة المعلومات، تحليل عينة الصوت فقط، ثم تحميل المقطع
# المختار بس — كله بدون أي ذكاء اصطناعي، وبدون تحميل الفيديو كامل.
# ----------------------------------------------------------------------------
def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _base_ydl_opts(cookies_path: str = None) -> dict:
    """
    إعدادات مشتركة بتقلل احتمال ظهور خطأ HTTP 403 Forbidden من يوتيوب.
    يوتيوب في الفترة الأخيرة بيشدّد إجراءات مكافحة البوتات، خصوصًا على
    IPs بتاعة سيرفرات الاستضافة السحابية (زي Streamlit Cloud)، فبنجرب
    كذا "عميل" مختلف (Android / iOS / mweb / web) وبنستخدم ملف الـ
    cookies لو المستخدم رفعه — ده أكتر حل موثوق حاليًا.
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "mweb", "web"],
            }
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            )
        },
    }
    if cookies_path and os.path.exists(cookies_path):
        opts["cookiefile"] = cookies_path
    return opts


def get_video_info(url: str, cookies_path: str = None):
    """بيجيب معلومات الفيديو (المدة أساسًا) من غير ما ينزّل أي حاجة خالص."""
    if yt_dlp is None:
        raise RuntimeError(
            "مكتبة yt-dlp مش متثبتة. ضيفها في requirements.txt: yt-dlp"
        )
    ydl_opts = {
        **_base_ydl_opts(cookies_path),
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    duration = info.get("duration")
    if not duration:
        raise RuntimeError("تعذّر تحديد مدة الفيديو من الرابط ده.")
    return float(duration), info


def download_audio_sample(url: str, workdir: str, cookies_path: str = None) -> str:
    """
    بينزّل الصوت بس (من غير الفيديو) عشان نحلل بيه — حجم الصوت أصغر بكتير
    من الفيديو، فده بيوفر وقت وباندويدث كبير قبل ما نحدد المقطع المطلوب.
    """
    if yt_dlp is None:
        raise RuntimeError(
            "مكتبة yt-dlp مش متثبتة. ضيفها في requirements.txt: yt-dlp"
        )
    out_template = os.path.join(workdir, "audio_sample.%(ext)s")
    ydl_opts = {
        **_base_ydl_opts(cookies_path),
        "format": "bestaudio/best",
        "outtmpl": out_template,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        if os.path.exists(path):
            return path
    raise RuntimeError("تعذّر تحميل عينة الصوت لتحليلها.")


def download_youtube_clip(
    url: str, start_seconds: float, end_seconds: float, workdir: str, cookies_path: str = None
) -> str:
    """
    بينزّل المقطع المطلوب بس (من `start_seconds` لـ `end_seconds`) مباشرة من
    يوتيوب من غير ما ينزّل الفيديو كامل، عن طريق خاصية download_ranges في
    yt-dlp (بتستخدم قدرة سيرفرات يوتيوب على تسليم "نطاق" زمني محدد فقط).
    """
    if yt_dlp is None:
        raise RuntimeError(
            "مكتبة yt-dlp مش متثبتة. ضيفها في requirements.txt: yt-dlp"
        )
    from yt_dlp.utils import download_range_func

    out_template = os.path.join(workdir, "clip.%(ext)s")
    ydl_opts = {
        **_base_ydl_opts(cookies_path),
        "format": "bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4]/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "download_ranges": download_range_func(None, [(start_seconds, end_seconds)]),
        "force_keyframes_at_cuts": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        mp4_path = os.path.splitext(path)[0] + ".mp4"
        if os.path.exists(mp4_path):
            return mp4_path
        if os.path.exists(path):
            return path
    raise RuntimeError("تعذّر تحميل المقطع من يوتيوب.")


def compute_loudness_profile(audio_path: str, workdir: str, window: float = ANALYSIS_WINDOW):
    """
    بيحوّل عينة الصوت لـ PCM خام (mono, 16-bit) عن طريق ffmpeg، وبعدين بيحسب
    متوسط الطاقة (RMS) لكل "بلاطة" زمنية بطول `window` ثانية باستخدام
    مكتبة array القياسية في بايثون (حساب متوسط تربيعي يدوي) — تحليل إشارة
    رقمي بحت، من غير أي نموذج تعلم آلي أو ذكاء اصطناعي.
    """
    wav_path = os.path.join(workdir, "audio.wav")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", audio_path,
            "-vn", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
            "-f", "wav", wav_path,
        ],
        check=True, capture_output=True,
    )

    with wave.open(wav_path, "rb") as wf:
        sample_rate = wf.getframerate()
        sample_width = wf.getsampwidth()
        frames_per_window = int(sample_rate * window)
        typecode = {1: "b", 2: "h", 4: "i"}.get(sample_width, "h")
        rms_values = []
        while True:
            frames = wf.readframes(frames_per_window)
            if not frames:
                break
            samples = array.array(typecode)
            # لو عدد البايتات مش مضاعف حجم العينة (آخر بلوك ناقص)، نتجاهل الباقي
            usable_len = len(frames) - (len(frames) % samples.itemsize)
            if usable_len <= 0:
                continue
            samples.frombytes(frames[:usable_len])
            if len(samples) == 0:
                continue
            sum_sq = sum(s * s for s in samples)
            rms = (sum_sq / len(samples)) ** 0.5
            rms_values.append(rms)

    return rms_values, window


def find_best_window(rms_values, window: float, clip_duration: float = CLIP_DURATION) -> float:
    """
    بيدوّر على أفضل نافذة مدتها `clip_duration` ثانية بأعلى متوسط طاقة صوت،
    باستخدام Prefix Sums + Sliding Window (خوارزمية رياضية بسيطة، O(n)).
    بيرجّع ثانية البداية المقترحة.
    """
    if not rms_values:
        return 0.0

    slices_per_clip = max(1, int(round(clip_duration / window)))
    n = len(rms_values)

    if n <= slices_per_clip:
        return 0.0

    prefix = [0] * (n + 1)
    for i, v in enumerate(rms_values):
        prefix[i + 1] = prefix[i] + v

    best_start_idx = 0
    best_sum = -1
    for start in range(0, n - slices_per_clip + 1):
        window_sum = prefix[start + slices_per_clip] - prefix[start]
        if window_sum > best_sum:
            best_sum = window_sum
            best_start_idx = start

    return best_start_idx * window


# ----------------------------------------------------------------------------
# حالة الجلسة
# ----------------------------------------------------------------------------
if "workdir" not in st.session_state:
    st.session_state.workdir = tempfile.mkdtemp(prefix="clip322_")
if "video_url" not in st.session_state:
    st.session_state.video_url = None
if "video_duration" not in st.session_state:
    st.session_state.video_duration = None
if "suggested_start" not in st.session_state:
    st.session_state.suggested_start = None
if "clip_path" not in st.session_state:
    st.session_state.clip_path = None
if "cookies_path" not in st.session_state:
    st.session_state.cookies_path = None

if not _ffmpeg_available():
    st.error(
        "ffmpeg مش متثبت على السيرفر. لازم تضيفه (مثلاً عن طريق packages.txt "
        "لو التطبيق شغال على Streamlit Community Cloud: اكتب فيه سطر واحد "
        "بكلمة ffmpeg)."
    )

# ----------------------------------------------------------------------------
# (اختياري) رفع ملف cookies.txt — يوتيوب في الفترة الأخيرة بيرفض كتير من
# طلبات التحميل من سيرفرات الاستضافة (Error 403)، وأكتر حل موثوق حاليًا إنك
# تدّي yt-dlp كوكيز من حساب يوتيوب حقيقي عشان يقتنع إن الطلب من متصفح فعلي.
# ----------------------------------------------------------------------------
with st.expander("🍪 (اختياري) رفع ملف cookies.txt — يحل مشاكل تحميل كتيرة"):
    st.caption(
        "لو بيظهرلك خطأ 403 Forbidden، صدّر ملف الكوكيز من متصفحك وانت داخل "
        "على حساب يوتيوب (فيه إضافات زي 'Get cookies.txt LOCALLY' لكروم أو "
        "'cookies.txt' لفايرفوكس) وارفعه هنا. الملف بيتخزن مؤقتًا على "
        "السيرفر بس وبيتمسح لما التطبيق يعيد التشغيل."
    )
    cookies_file = st.file_uploader("ملف cookies.txt", type=["txt"], label_visibility="collapsed")
    if cookies_file is not None:
        cookies_save_path = os.path.join(st.session_state.workdir, "cookies.txt")
        with open(cookies_save_path, "wb") as f:
            f.write(cookies_file.getvalue())
        st.session_state.cookies_path = cookies_save_path
        st.success("تم حفظ ملف الكوكيز وهيتستخدم في التحميل.")

# ----------------------------------------------------------------------------
# خطوة 1: تحليل خفيف — من غير تحميل الفيديو خالص
# بنجيب مدة الفيديو بس (بدون تحميل)، وبعدين ننزّل الصوت وحده (مش الفيديو)
# عشان نحلله ونقترح أقوى 60 ثانية.
# ----------------------------------------------------------------------------
with st.form("analyze_form"):
    youtube_url = st.text_input(
        "لينك فيديو اليوتيوب",
        placeholder="https://www.youtube.com/watch?v=...",
        label_visibility="collapsed",
    )
    analyze_submitted = st.form_submit_button("🔎 تحليل الفيديو (من غير تحميله كامل)")

if analyze_submitted:
    if not youtube_url.strip():
        st.warning("من فضلك، حط لينك يوتيوب الأول.")
    else:
        clean_url = youtube_url.strip()
        cookies_path = st.session_state.cookies_path
        try:
            with st.spinner("جاري جلب معلومات الفيديو..."):
                duration, _info = get_video_info(clean_url, cookies_path)

            if duration <= CLIP_DURATION:
                st.warning(
                    f"مدة الفيديو ({int(duration)} ثانية) أقل من أو تساوي "
                    f"{CLIP_DURATION} ثانية أصلاً."
                )

            st.session_state.video_url = clean_url
            st.session_state.video_duration = duration
            st.session_state.clip_path = None

            with st.spinner("جاري تحميل الصوت بس (بدون الفيديو) لتحليله..."):
                audio_path = download_audio_sample(clean_url, st.session_state.workdir, cookies_path)

            with st.spinner("جاري تحليل الصوت لإيجاد أقوى 60 ثانية..."):
                rms_values, window = compute_loudness_profile(audio_path, st.session_state.workdir)
                best_start = find_best_window(rms_values, window, CLIP_DURATION)
                st.session_state.suggested_start = best_start

            # مسح عينة الصوت بعد التحليل، مش محتاجينها تاني
            try:
                os.remove(audio_path)
            except OSError:
                pass

            st.success("تم التحليل! اضبط نقطة البداية لو حابب، وبعدين حمّل المقطع بس.")
        except Exception as e:
            st.error(f"فشل التحليل: {e}")
            if "403" in str(e) or "Forbidden" in str(e):
                st.info(
                    "غالبًا الحل: افتح قسم '🍪 رفع ملف cookies.txt' فوق وارفع "
                    "كوكيز من حساب يوتيوب حقيقي، وجرب تاني."
                )
            with st.expander("تفاصيل تقنية (للمطوّر)"):
                st.code(traceback.format_exc())

# ----------------------------------------------------------------------------
# خطوة 2: اختيار/تعديل نقطة البداية، وبعدين تحميل المقطع المختار بس
# (الفيديو الأصلي بالكامل من غير ما يتحمل خالص)
# ----------------------------------------------------------------------------
if st.session_state.video_url and st.session_state.video_duration:
    duration = st.session_state.video_duration
    max_start = max(0.0, duration - 1)
    default_start = min(st.session_state.suggested_start or 0.0, max_start)

    st.markdown("#### ✂️ اضبط بداية المقطع")
    start_seconds = st.slider(
        "ثانية البداية",
        min_value=0.0,
        max_value=float(max_start),
        value=float(default_start),
        step=1.0,
        format="%.0f ثانية",
        label_visibility="collapsed",
    )

    remaining = duration - start_seconds
    clip_len = min(CLIP_DURATION, remaining)
    st.caption(
        f"⏱️ هيتحمّل من الثانية {int(start_seconds)} لمدة {int(clip_len)} ثانية بس "
        f"(مدة الفيديو الكلية: {int(duration)} ثانية) — من غير تحميل باقي الفيديو."
    )

    if st.button("⬇️ حمّل المقطع بس"):
        with st.spinner("جاري تحميل المقطع المختار بس من يوتيوب..."):
            try:
                clip_path = download_youtube_clip(
                    st.session_state.video_url,
                    start_seconds,
                    start_seconds + clip_len,
                    st.session_state.workdir,
                    st.session_state.cookies_path,
                )
                st.session_state.clip_path = clip_path
            except Exception as e:
                st.error(f"فشل تحميل المقطع: {e}")
                if "403" in str(e) or "Forbidden" in str(e):
                    st.info(
                        "غالبًا الحل: افتح قسم '🍪 رفع ملف cookies.txt' فوق وارفع "
                        "كوكيز من حساب يوتيوب حقيقي، وجرب تاني."
                    )
                with st.expander("تفاصيل تقنية (للمطوّر)"):
                    st.code(traceback.format_exc())

if st.session_state.clip_path and os.path.exists(st.session_state.clip_path):
    st.success("تم تحميل المقطع بنجاح!")
    st.video(st.session_state.clip_path)
    with open(st.session_state.clip_path, "rb") as f:
        st.download_button(
            "⬇️ حفظ المقطع على جهازك (mp4)",
            data=f.read(),
            file_name="clip_60s.mp4",
            mime="video/mp4",
        )
