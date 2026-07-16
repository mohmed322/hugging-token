"""
مولّد فيديو بالذكاء الاصطناعي — LTX-2.3 (فيديو + صوت معًا)
==========================================================
تطبيق Streamlit بيتصل بـ Hugging Face Space المجانية الرسمية لموديل LTX-2.3
الخاص بـ Lightricks (Lightricks/LTX-2-3) عن طريق gradio_client، عشان يولّد
فيديو قصير (بالصوت) من وصف نصي، من غير ما تحتاج كرت شاشة مدفوع — التوليد
بيحصل على السيرفرات المجانية بتاعة الـ Space نفسها (ZeroGPU).

ملاحظة مهمة:
------------
Hugging Face Spaces أحيانًا بتغيّر اسم الـ endpoint أو ترتيب المدخلات الداخلية
بتاعتها مع تحديثات الموديل. الكود هنا مكتوب على أساس شكل الواجهة الحالي للـ
Space (صورة اختيارية + Prompt + مدة بالثواني من 1 لـ 10 + تحسين الوصف + دقة
عالية). لو حصل خطأ عند الاتصال، الكود هيطبعلك تلقائيًا توصيف الـ API الحالي
(عن طريق client.view_api) في رسالة الخطأ عشان تظبط الأسماء/الترتيب بسهولة
من غير ما تدور بنفسك.

ملاحظة على التصميم:
-------------------
منطق الاتصال بالموديل وتوليد الفيديو (generate_video / get_client /
_find_video_path) زي ما هو بالظبط من غير أي تعديل. اللي اتغيّر بس:
- الشكل (الخلفية الفضائية + عناصر شفافة بدل الصناديق).
- خيارَي "تحسين الوصف" و"الدقة العالية" بقوا قيمة ثابتة (True / False) بدل ما
  يكونوا صناديق ظاهرة في الواجهة، بناءً على طلبك بإخفاء أي صناديق/أزرار زيادة.
  لو حابب ترجّعهم ظاهرين تاني قولّي.
"""

import os
import random
import traceback

import streamlit as st
from gradio_client import Client

# ----------------------------------------------------------------------------
# إعدادات عامة
# ----------------------------------------------------------------------------
HF_SPACE_ID = "Lightricks/LTX-2-3"  # الـ Space الرسمية لـ LTX-2.3 (Lightricks)
MIN_DURATION, MAX_DURATION = 1, 10  # ثواني، حسب حدود الـ Space نفسها
DEFAULT_DURATION = 5

# قيم ثابتة بدل الصناديق اللي اتشالت من الواجهة (منطق التوليد نفسه لسه زي ما هو)
ENHANCE_PROMPT_DEFAULT = True
HIGH_RESOLUTION_DEFAULT = False


def _get_hf_token():
    """بيجيب الـ Hugging Face Token من متغيرات البيئة أو من secrets.toml (اختياري)."""
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    try:
        return st.secrets.get("HF_TOKEN")
    except Exception:
        return None


HF_TOKEN = _get_hf_token()

st.set_page_config(page_title="مولّد فيديو LTX-2.3", page_icon="🎬", layout="centered")

# ----------------------------------------------------------------------------
# توليد مواقع النجوم والعناصر العائمة عشوائيًا مرة واحدة بس (وحفظها في
# الجلسة) عشان الخلفية متبقاش بتتغيّر شكلها كل مرة الصفحة بتعمل rerun
# ----------------------------------------------------------------------------
def _make_star_shadows(count, opacity_min, opacity_max):
    random.seed(count * 7919)
    shadows = []
    for _ in range(count):
        x = round(random.uniform(0, 100), 2)
        y = round(random.uniform(0, 100), 2)
        o = round(random.uniform(opacity_min, opacity_max), 2)
        shadows.append(f"{x}vw {y}vh rgba(255,255,255,{o})")
    return ", ".join(shadows)


def _make_floaters():
    """عناصر عائمة (رواد فضاء + كواكب) بتعدي الشاشة من اليمين للشمال وبترجع
    تاني من الأول (loop لا نهائي حقيقي)، مع فروقات في التوقيت عشان الحركة
    تفضل مستمرة على الشاشة من غير ما تختفي فترات طويلة."""
    random.seed(4242)
    colors = ["#7c5cff", "#38bdf8", "#f472b6", "#fb923c", "#34d399"]
    floaters = []

    # رواد فضاء
    n_astro = 5
    for i in range(n_astro):
        floaters.append({
            "type": "astro",
            "top": round(random.uniform(6, 90), 1),
            "size": random.randint(24, 36),
            "duration": round(random.uniform(16, 26), 1),
            "delay": round(-(i / n_astro) * 22, 1),
        })

    # كواكب
    n_planet = 7
    for i in range(n_planet):
        floaters.append({
            "type": "planet",
            "top": round(random.uniform(4, 94), 1),
            "size": random.randint(16, 36),
            "duration": round(random.uniform(18, 32), 1),
            "delay": round(-(i / n_planet) * 26, 1),
            "color": colors[i % len(colors)],
        })

    return floaters


if "star_shadows" not in st.session_state:
    st.session_state.star_shadows = {
        "small": _make_star_shadows(160, 0.15, 0.45),
        "medium": _make_star_shadows(70, 0.35, 0.7),
        "large": _make_star_shadows(28, 0.6, 0.95),
    }

if "floaters" not in st.session_state:
    st.session_state.floaters = _make_floaters()

_stars = st.session_state.star_shadows
_floaters = st.session_state.floaters


def _astro_svg(size):
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 34 34" style="animation: tumble 9s ease-in-out infinite;">
        <ellipse cx="17" cy="20" rx="8" ry="10" fill="#e5e7eb"/>
        <circle cx="17" cy="10" r="8" fill="#f5f5f7"/>
        <circle cx="17" cy="10" r="5.5" fill="#7c5cff" opacity="0.55"/>
        <rect x="4" y="17" width="6" height="3" rx="1.5" fill="#cbd5e1"/>
        <rect x="24" y="17" width="6" height="3" rx="1.5" fill="#cbd5e1"/>
    </svg>"""


_floaters_html = ""
for f in _floaters:
    if f["type"] == "astro":
        _floaters_html += (
            f'<div class="floater" style="top:{f["top"]}%; right:-8vw; '
            f'width:{f["size"]}px; height:{f["size"]}px; '
            f'animation-duration:{f["duration"]}s; animation-delay:{f["delay"]}s;">'
            f'{_astro_svg(f["size"])}</div>'
        )
    else:
        s = f["size"]
        shadow = f"inset -{round(s*0.25,1)}px -{round(s*0.2,1)}px 0 rgba(0,0,0,0.25), 0 0 {round(s*0.4,1)}px rgba(255,255,255,0.15)"
        _floaters_html += (
            f'<div class="floater planet" style="top:{f["top"]}%; right:-8vw; '
            f'width:{s}px; height:{s}px; background:{f["color"]}; box-shadow:{shadow}; '
            f'animation-duration:{f["duration"]}s; animation-delay:{f["delay"]}s;"></div>'
        )

# ----------------------------------------------------------------------------
# التنسيق (CSS) — خلفية فضائية + عناصر شفافة بالكامل بدون صناديق
# ----------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    header[data-testid="stHeader"] {{ display: none !important; }}
    #MainMenu {{ visibility: hidden !important; }}
    footer {{ visibility: hidden !important; }}

    :root {{
        --bg: #05060a;
        --text-primary: #ffffff;
        --text-secondary: #d7dae0;
        --glass-bg: rgba(255,255,255,0.045);
        --glass-border: rgba(255,255,255,0.16);
        --glass-border-hover: rgba(255,255,255,0.32);
    }}

    .stApp {{ background: var(--bg) !important; }}
    .block-container {{
        max-width: 640px;
        margin: 0 auto;
        padding: 2.5rem 1.2rem !important;
        position: relative;
        z-index: 2;
    }}

    * {{ color: var(--text-primary); }}

    /* خلفية النجوم الثابتة */
    .space-bg {{
        position: fixed;
        inset: 0;
        z-index: 0;
        background: var(--bg);
        overflow: hidden;
        pointer-events: none;
    }}
    .stars-layer {{
        position: absolute;
        top: 0; left: 0;
        width: 2px; height: 2px;
        border-radius: 50%;
        background: transparent;
    }}
    .stars-small {{ box-shadow: {_stars["small"]}; animation: twinkle 3s ease-in-out infinite alternate; }}
    .stars-medium {{ box-shadow: {_stars["medium"]}; animation: twinkle 4s ease-in-out infinite alternate-reverse; }}
    .stars-large {{ box-shadow: {_stars["large"]}; animation: twinkle 2.4s ease-in-out infinite alternate; }}

    @keyframes twinkle {{
        from {{ opacity: 0.55; }}
        to {{ opacity: 1; }}
    }}

    /* عناصر عائمة بتعدي الشاشة من اليمين للشمال وبتلف تاني بشكل متصل بلا نهاية */
    .floater {{
        position: fixed;
        z-index: 1;
        pointer-events: none;
        animation-name: floatX;
        animation-timing-function: linear;
        animation-iteration-count: infinite;
    }}
    @keyframes floatX {{
        from {{ transform: translateX(0); }}
        to {{ transform: translateX(-135vw); }}
    }}
    .planet {{ border-radius: 50%; opacity: 0.85; }}
    @keyframes tumble {{
        from {{ transform: rotate(-8deg); }}
        to {{ transform: rotate(8deg); }}
    }}

    /* الهيدر */
    .app-header {{ text-align: center; margin-bottom: 1.8rem; }}
    .app-header h1 {{
        font-size: 1.9rem;
        font-weight: 800;
        letter-spacing: 1px;
        margin-bottom: 0.3rem;
        color: #fff;
        text-shadow: 0 0 10px rgba(255,255,255,0.55), 0 0 22px rgba(255,255,255,0.3), 0 0 38px rgba(255,255,255,0.15);
        animation: logoGlow 2.2s ease-in-out infinite alternate;
    }}
    .app-header p {{
        color: var(--text-secondary) !important;
        font-size: 0.92rem;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
    }}
    @keyframes logoGlow {{
        from {{ text-shadow: 0 0 8px rgba(255,255,255,0.4), 0 0 16px rgba(255,255,255,0.22), 0 0 28px rgba(255,255,255,0.1); }}
        to {{ text-shadow: 0 0 13px rgba(255,255,255,0.7), 0 0 26px rgba(255,255,255,0.4), 0 0 44px rgba(255,255,255,0.2); }}
    }}
    .app-badge {{
        display: inline-block;
        background: var(--glass-bg);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        border: 1px solid var(--glass-border);
        color: #fff !important;
        padding: 4px 14px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
    }}

    /* الفورم شفاف بدون أي صندوق حوله */
    div[data-testid="stForm"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }}

    /* صندوق كتابة الوصف — شفاف بالكامل */
    div[data-testid="stTextArea"] textarea {{
        background: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 16px !important;
        color: #fff !important;
        direction: auto !important;
        unicode-bidi: plaintext !important;
        text-align: start !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        box-shadow: none !important;
    }}
    div[data-testid="stTextArea"] textarea:focus {{
        border-color: var(--glass-border-hover) !important;
        box-shadow: 0 0 0 1px var(--glass-border-hover) !important;
    }}
    div[data-testid="stTextArea"] textarea::placeholder {{
        color: rgba(255,255,255,0.45) !important;
    }}
    div[data-testid="stTextArea"] label p {{ color: #fff !important; }}

    /* صندوق اختيار المدة — شفاف وصغير */
    div[data-testid="stSelectbox"] > label p {{ color: #fff !important; }}
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
        background: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 999px !important;
        color: #fff !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
    }}
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {{
        border-color: var(--glass-border-hover) !important;
    }}
    div[data-testid="stSelectbox"] svg {{ fill: #fff !important; }}
    ul[data-testid="stVirtualDropdown"], div[data-baseweb="popover"] ul {{
        background: #0d0e14 !important;
        border: 1px solid var(--glass-border) !important;
    }}
    ul[data-testid="stVirtualDropdown"] li, div[data-baseweb="popover"] li {{
        color: #fff !important;
    }}

    /* زرار إنشاء الفيديو — شفاف زي الباقي */
    .stButton button, div[data-testid="stForm"] button[kind="primary"] {{
        background: var(--glass-bg) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        color: #fff !important;
        border-radius: 999px !important;
        font-weight: 700 !important;
        padding: 0.65rem 1.4rem !important;
        border: 1px solid var(--glass-border) !important;
        width: 100%;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
        box-shadow: none !important;
    }}
    .stButton button:hover, div[data-testid="stForm"] button[kind="primary"]:hover {{
        border-color: var(--glass-border-hover) !important;
    }}

    .stDownloadButton button {{
        background: var(--glass-bg) !important;
        color: #fff !important;
        border-radius: 999px !important;
        font-weight: 700 !important;
        border: 1px solid var(--glass-border) !important;
        width: 100%;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
    }}

    /* رسائل النجاح/الخطأ/التحذير */
    div[data-testid="stAlert"] {{
        background: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        color: #fff !important;
    }}
    div[data-testid="stAlert"] p {{ color: #fff !important; }}

    /* استجابة للموبايل */
    @media (max-width: 640px) {{
        .block-container {{ padding: 1.6rem 0.9rem !important; }}
        .app-header h1 {{ font-size: 1.5rem; }}
        .floater {{ transform: scale(0.85); }}
    }}
    </style>

    <div class="space-bg">
        <div class="stars-layer stars-small"></div>
        <div class="stars-layer stars-medium"></div>
        <div class="stars-layer stars-large"></div>
    </div>

    {_floaters_html}
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# رأس الصفحة
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <span class="app-badge">مدعوم بنموذج LTX-2.3</span>
        <h1>🎬 مولّد فيديو بالذكاء الاصطناعي</h1>
        <p>اكتب وصف الفيديو اللي في خيالك، وهيتولّد لك فيديو قصير بالصوت مباشرة</p>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def get_client():
    """بيعمل اتصال واحد بس بالـ Space ويحتفظ بيه (Client بيتعمل مرة واحدة)."""
    return Client(HF_SPACE_ID, token=HF_TOKEN)


def _find_video_path(result):
    """بيدور جوه رد الـ API (اللي ممكن يكون tuple/list/dict) عن أول مسار فيديو
    حقيقي موجود على القرص (gradio_client بينزّل الملفات محليًا تلقائيًا)."""

    def is_valid_path(x):
        return isinstance(x, str) and os.path.exists(x)

    if is_valid_path(result):
        return result

    if isinstance(result, dict):
        for value in result.values():
            found = _find_video_path(value)
            if found:
                return found

    if isinstance(result, (list, tuple)):
        for item in result:
            found = _find_video_path(item)
            if found:
                return found

    return None


def generate_video(prompt: str, duration: int, enhance_prompt: bool, high_resolution: bool):
    """بيبعت الطلب لـ Space الـ LTX-2.3 ويرجّع مسار الفيديو الناتج (mp4) محليًا."""
    client = get_client()
    # الأبعاد الافتراضية للـ Space: 1024x1536 عادي، وبنكبّرها شوية للدقة العالية
    height, width = (1536, 2048) if high_resolution else (1024, 1536)
    try:
        result = client.predict(
            input_image=None,          # الصورة الاختيارية لتوجيه الحركة — مش مستخدمة هنا
            prompt=prompt,              # وصف الفيديو (Prompt)
            duration=float(duration),   # المدة بالثواني (رقم عشري بين 1.0 و 10.0)
            enhance_prompt=enhance_prompt,  # تحسين الوصف تلقائيًا
            seed=10,
            randomize_seed=True,         # نسيب Seed عشوائي كل مرة عشان نتايج متنوعة
            height=height,
            width=width,
            api_name="/generate_video",
        )
    except Exception as first_error:
        # لو الـ endpoint أو ترتيب المدخلات اتغيّر في الـ Space، نطبع توصيف
        # الـ API الحالي عشان تقدر تظبط الأسماء بسهولة من غير ما تدوّر بنفسك.
        try:
            api_info = client.view_api(print_info=False, return_format="dict")
        except Exception:
            api_info = "تعذّر جلب توصيف الـ API أيضًا — تأكد من اتصال الإنترنت أو من اسم الـ Space."
        raise RuntimeError(
            "فشل الاتصال بنموذج LTX-2.3.\n\n"
            f"تفاصيل الخطأ الأصلي: {first_error}\n\n"
            "توصيف الـ API الحالي للـ Space (استخدمه لتعديل أسماء/ترتيب "
            f"المدخلات في دالة generate_video):\n{api_info}"
        ) from first_error

    video_path = _find_video_path(result)
    if not video_path:
        raise RuntimeError(f"تم الاتصال بنجاح لكن تعذّر إيجاد ملف الفيديو في الرد: {result}")

    return video_path


# ----------------------------------------------------------------------------
# واجهة الإدخال — 3 عناصر بس: صندوق الوصف، صندوق المدة، زرار الإنشاء
# ----------------------------------------------------------------------------
with st.form("video_form"):
    prompt = st.text_area(
        "وصف الفيديو (Prompt)",
        placeholder="مثال: رائد فضاء يمشي ببطء على سطح القمر، غبار ناعم يتطاير حول قدميه، إضاءة سينمائية...",
        height=130,
    )

    duration = st.selectbox(
        "مدة الفيديو",
        options=list(range(MIN_DURATION, MAX_DURATION + 1)),
        index=DEFAULT_DURATION - MIN_DURATION,
        format_func=lambda d: f"{d} ثواني",
    )

    submitted = st.form_submit_button("إنشاء الفيديو")

# ----------------------------------------------------------------------------
# التوليد والعرض
# ----------------------------------------------------------------------------
if submitted:
    if not prompt.strip():
        st.warning("من فضلك، اكتب وصف الفيديو الأول.")
    else:
        with st.spinner("جاري توليد الفيديو والصوت... ممكن تاخد شوية وقت حسب المدة المطلوبة ⏳"):
            try:
                video_path = generate_video(
                    prompt=prompt.strip(),
                    duration=duration,
                    enhance_prompt=ENHANCE_PROMPT_DEFAULT,
                    high_resolution=HIGH_RESOLUTION_DEFAULT,
                )
                st.success("تم إنتاج الفيديو بنجاح! 🎉")
                st.video(video_path)
                with open(video_path, "rb") as f:
                    st.download_button(
                        "⬇️ تحميل الفيديو (mp4)",
                        data=f.read(),
                        file_name="ltx_video.mp4",
                        mime="video/mp4",
                    )
            except Exception as e:
                st.error(str(e))
                with st.expander("تفاصيل تقنية (للمطوّر)"):
                    st.code(traceback.format_exc())
