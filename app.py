"""
مولّد فيديو بالذكاء الاصطناعي — LTX-2.3 (فيديو + صوت معًا)
==========================================================
تطبيق Streamlit بتصميم فضائي (خلفية سودا + نجوم متحركة + رائد فضاء وكواكب
بتظهر بين فترة وفترة) بيتصل بـ Hugging Face Space المجانية الرسمية لموديل
LTX-2.3 الخاص بـ Lightricks (Lightricks/LTX-2-3) عن طريق gradio_client.

ملاحظة مهمة:
------------
Hugging Face Spaces أحيانًا بتغيّر اسم الـ endpoint أو ترتيب المدخلات
الداخلية بتاعتها مع تحديثات الموديل. لو حصل خطأ عند الاتصال، الكود هيطبعلك
تلقائيًا توصيف الـ API الحالي (عن طريق client.view_api) في رسالة الخطأ عشان
تظبط الأسماء/الترتيب بسهولة من غير ما تدوّر بنفسك.
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

st.set_page_config(page_title="322", page_icon="🌌", layout="centered")

# ----------------------------------------------------------------------------
# توليد نمط النجوم (ثابت، بدون JavaScript، عشان يشتغل بثبات جوه Streamlit)
# بنعمل "بلاطة" واحدة من النجوم بإحداثيات عشوائية ثابتة (بذرة ثابتة)، وبعدين
# بنكررها مرتين جنب بعض بالظبط، وبنحرك الاتنين مع بعض بمقدار عرض بلاطة واحدة
# فقط — عشان لما توصل البلاطة الأولى لنص المشهد، الثانية (المطابقة ليها 100%)
# تكون وصلت لنفس المكان بالظبط، فمفيش أي إحساس بقطع أو إعادة تشغيل المشهد.
# ----------------------------------------------------------------------------
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

# ملحوظة: الكود ده لازم يتكتب كله في سطر واحد من غير أي مسافات بادئة أو أسطر
# فاضية جواه — لو اتقسم على أسطر متساحبة، Streamlit ممكن يفهمه غلط كـ"كود نصي"
# بدل ما يرسمه كعنصر HTML فعلي (وده اللي كان بيسبب ظهور الكود كنص على الصفحة).
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
# CSS — الثيم الفضائي الكامل (خلفية، نجوم متحركة، زجاج شفاف للعناصر)
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

    /* ---------------- الخلفية الفضائية ---------------- */
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

    /* رائد الفضاء: بيظهر ويعبر الشاشة من اليمين للشمال كل ~17 ثانية */
    .astronaut {
        position: absolute;
        top: 18%;
        animation: crossFar 17s linear infinite;
    }
    .astronaut svg { animation: tumble 6s ease-in-out infinite alternate; }
    @keyframes tumble { from { transform: rotate(-8deg); } to { transform: rotate(8deg); } }

    /* الكواكب: كل واحد بمدة وتأخير مختلف عشان ظهورهم يبان عشوائي */
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

    /* الظهور مش دايم: العنصر بيفضل مخفي/برّه الشاشة أغلب دورة الحركة، وبيعبر
       الشاشة بس في جزء بسيط منها — فيبان بشكل متقطع كل ~15-20 ثانية */
    @keyframes crossFar {
        0%   { left: 110%; opacity: 0; }
        55%  { left: 110%; opacity: 0; }
        60%  { opacity: 1; }
        92%  { left: -15%; opacity: 1; }
        100% { left: -15%; opacity: 0; }
    }

    /* ---------------- شعار 322 ---------------- */
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

    /* ---------------- عناصر زجاجية شفافة (Glassmorphism) ---------------- */
    div[data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }

    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextArea"] div[data-baseweb="textarea"],
    div[data-testid="stTextArea"] div[data-baseweb="textarea"] textarea,
    div[class*="stTextArea"] textarea,
    textarea {
        background: rgba(255,255,255,0.04) !important;
        background-color: rgba(255,255,255,0.04) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        border: 1px solid rgba(255,255,255,0.14) !important;
        box-shadow: none !important;
        border-radius: 22px !important;
        color: #ffffff !important;
    }
    textarea {
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
    }
    textarea::placeholder {
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
    '<p>اكتب وصف الفيديو اللي في خيالك</p></div>',
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def get_client():
    """بيعمل اتصال واحد بس بالـ Space ويحتفظ بيه (Client بيتعمل مرة واحدة)."""
    return Client(HF_SPACE_ID, token=HF_TOKEN)


def _find_video_path(result):
    """بيدور جوه رد الـ API عن أول مسار فيديو حقيقي موجود على القرص
    (gradio_client بينزّل الملفات محليًا تلقائيًا)."""

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
            input_image=None,              # الصورة الاختيارية لتوجيه الحركة — مش مستخدمة هنا
            prompt=prompt,                  # وصف الفيديو (Prompt)
            duration=float(duration),       # المدة بالثواني (رقم عشري بين 1.0 و 10.0)
            enhance_prompt=enhance_prompt,   # تحسين الوصف تلقائيًا
            seed=10,
            randomize_seed=True,             # نسيب Seed عشوائي كل مرة عشان نتايج متنوعة
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
# واجهة الإدخال
# ----------------------------------------------------------------------------
with st.form("video_form"):
    prompt = st.text_area(
        "وصف الفيديو",
        placeholder="مثال: رائد فضاء يمشي ببطء على سطح القمر، غبار ناعم يتطاير حول قدميه، إضاءة سينمائية...",
        height=130,
        label_visibility="collapsed",
    )

    col_duration, _ = st.columns([1, 2])
    with col_duration:
        duration = st.selectbox(
            "المدة",
            options=list(range(MIN_DURATION, MAX_DURATION + 1)),
            index=DEFAULT_DURATION - MIN_DURATION,
            format_func=lambda n: f"{n} ثواني",
        )

    with st.expander("⚙️ إعدادات متقدمة"):
        enhance_prompt = st.checkbox("تحسين الوصف تلقائيًا (Enhance Prompt)", value=True)
        high_resolution = st.checkbox("دقة عالية (أبطأ في التوليد)", value=False)

    submitted = st.form_submit_button("إنشاء الفيديو")

# CSS إضافي بيتحمّل هنا (بعد إنشاء العناصر فوق) عشان يكون آخر حاجة في الصفحة،
# فيغلب على تنسيق Streamlit/BaseWeb الداخلي اللي بيتحمّل بعد أي CSS نحطه فوق.
st.markdown(
    """
    <style>
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextArea"] div[data-baseweb="textarea"],
    div[data-testid="stTextArea"] div[data-baseweb="textarea"] textarea {
        background: rgba(255,255,255,0.04) !important;
        background-color: rgba(255,255,255,0.04) !important;
        backdrop-filter: blur(6px) !important;
        -webkit-backdrop-filter: blur(6px) !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        box-shadow: none !important;
        border-radius: 22px !important;
        color: #ffffff !important;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6) !important;
    }
    div[data-testid="stTextArea"] textarea::placeholder {
        color: rgba(255,255,255,0.55) !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"],
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] div[role="combobox"] {
        background: rgba(255,255,255,0.04) !important;
        background-color: rgba(255,255,255,0.04) !important;
        backdrop-filter: blur(6px) !important;
        -webkit-backdrop-filter: blur(6px) !important;
        border-color: rgba(255,255,255,0.14) !important;
        box-shadow: none !important;
        border-radius: 14px !important;
    }
    div[data-testid="stSelectbox"] * {
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# التوليد والعرض
# ----------------------------------------------------------------------------
if submitted:
    if not prompt.strip():
        st.warning("من فضلك، اكتب وصف الفيديو الأول.")
    else:
        with st.spinner("جاري توليد الفيديو والصوت... ممكن تاخد شوية وقت حسب المدة المطلوبة"):
            try:
                video_path = generate_video(
                    prompt=prompt.strip(),
                    duration=duration,
                    enhance_prompt=enhance_prompt,
                    high_resolution=high_resolution,
                )
                st.success("تم إنتاج الفيديو بنجاح!")
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
