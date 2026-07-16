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
الجزء ده بس هو اللي اتغيّر (شكل الصفحة/الـ CSS/الخلفية الفضائية). منطق
الاتصال بالموديل وتوليد الفيديو (generate_video / get_client / _find_video_path)
والفورم نفسه (الحقول والأزرار) زي ما هو بالظبط من غير أي تعديل.
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

st.set_page_config(page_title="مولّد فيديو LTX-2.3", page_icon="🎬", layout="centered")

# ----------------------------------------------------------------------------
# توليد مواقع النجوم عشوائيًا مرة واحدة بس (وحفظها في الجلسة) عشان
# النجوم متبقاش بتقفز مكانها كل مرة الصفحة بتعمل rerun
# ----------------------------------------------------------------------------
def _make_star_shadows(count, opacity_min, opacity_max):
    random.seed(count * 7919)  # ثابت لكل حجم عشان النتيجة تفضل زي ما هي
    shadows = []
    for _ in range(count):
        x = round(random.uniform(0, 100), 2)
        y = round(random.uniform(0, 100), 2)
        o = round(random.uniform(opacity_min, opacity_max), 2)
        shadows.append(f"{x}vw {y}vh rgba(255,255,255,{o})")
    return ", ".join(shadows)


if "star_shadows" not in st.session_state:
    st.session_state.star_shadows = {
        "small": _make_star_shadows(160, 0.15, 0.45),
        "medium": _make_star_shadows(70, 0.35, 0.7),
        "large": _make_star_shadows(28, 0.6, 0.95),
    }

_stars = st.session_state.star_shadows

# ----------------------------------------------------------------------------
# التنسيق (CSS) — ثيم فضائي غامق (خلفية سودا + نجوم + عناصر عائمة)
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
        --text-secondary: #cbd0da;
        --accent: #7c5cff;
        --card-bg: rgba(255,255,255,0.04);
        --card-border: rgba(255,255,255,0.14);
        --button-bg: rgba(255,255,255,0.04);
        --button-text: #ffffff;
    }}

    .stApp {{ background: var(--bg) !important; }}
    .block-container {{ max-width: 720px; margin: 0 auto; padding-top: 2.5rem !important; position: relative; z-index: 2; }}

    h1, h2, h3, p, label, span, div {{ color: var(--text-primary); }}

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

    /* عناصر عائمة (رائد فضاء وكواكب) بتعدي الشاشة بحركة CSS بحتة */
    .floater {{
        position: fixed;
        z-index: 1;
        pointer-events: none;
        animation-name: floatX;
        animation-timing-function: linear;
        animation-iteration-count: infinite;
    }}
    @keyframes floatX {{
        from {{ transform: translateX(6vw); }}
        to {{ transform: translateX(-130vw); }}
    }}
    .planet {{
        border-radius: 50%;
        opacity: 0.85;
    }}
    @keyframes tumble {{
        from {{ transform: rotate(-8deg); }}
        to {{ transform: rotate(8deg); }}
    }}

    .app-header {{
        text-align: center;
        margin-bottom: 1.8rem;
    }}
    .app-header h1 {{
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 1px;
        margin-bottom: 0.3rem;
        text-shadow: 0 0 10px rgba(255,255,255,0.55), 0 0 22px rgba(255,255,255,0.3), 0 0 38px rgba(255,255,255,0.15);
        animation: logoGlow 2.2s ease-in-out infinite alternate;
    }}
    .app-header p {{
        color: var(--text-secondary) !important;
        font-size: 0.95rem;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
    }}
    @keyframes logoGlow {{
        from {{ text-shadow: 0 0 8px rgba(255,255,255,0.4), 0 0 16px rgba(255,255,255,0.22), 0 0 28px rgba(255,255,255,0.1); }}
        to {{ text-shadow: 0 0 13px rgba(255,255,255,0.7), 0 0 26px rgba(255,255,255,0.4), 0 0 44px rgba(255,255,255,0.2); }}
    }}
    .app-badge {{
        display: inline-block;
        background: var(--card-bg);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        border: 1px solid var(--card-border);
        color: #fff !important;
        padding: 4px 14px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
    }}

    /* الفورم كبطاقة زجاجية */
    div[data-testid="stForm"] {{
        background: var(--card-bg) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        border: 1px solid var(--card-border) !important;
        border-radius: 20px !important;
        padding: 1.6rem !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.35);
    }}

    div[data-testid="stForm"] textarea {{
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 12px !important;
        color: #fff !important;
        direction: auto !important;
        unicode-bidi: plaintext !important;
        text-align: start !important;
    }}
    div[data-testid="stForm"] textarea::placeholder {{
        color: rgba(255,255,255,0.45) !important;
    }}

    /* السلايدر */
    div[data-testid="stSlider"] [data-baseweb="slider"] div {{ background-color: var(--accent) !important; }}
    div[data-testid="stSliderTickBarMin"], div[data-testid="stSliderTickBarMax"] {{ color: var(--text-secondary) !important; }}

    /* الـ expander (إعدادات متقدمة) */
    div[data-testid="stExpander"] {{
        background: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 14px !important;
    }}
    div[data-testid="stExpander"] summary {{ color: #fff !important; }}

    /* الأزرار */
    .stButton button, div[data-testid="stForm"] button[kind="primary"] {{
        background: var(--button-bg) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        color: var(--button-text) !important;
        border-radius: 999px !important;
        font-weight: 700 !important;
        padding: 0.6rem 1.4rem !important;
        border: 1px solid var(--card-border) !important;
        width: 100%;
        text-shadow: 0 1px 3px rgba(0,0,0,0.6);
    }}
    .stButton button:hover, div[data-testid="stForm"] button[kind="primary"]:hover {{
        border-color: rgba(255,255,255,0.35) !important;
    }}

    .stDownloadButton button {{
        background-color: var(--accent) !important;
        color: #fff !important;
        border-radius: 999px !important;
        font-weight: 700 !important;
        border: none !important;
        width: 100%;
    }}

    /* رسائل النجاح/الخطأ/التحذير تتوافق مع الثيم الغامق */
    div[data-testid="stAlert"] {{
        background: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
    }}
    </style>

    <div class="space-bg">
        <div class="stars-layer stars-small"></div>
        <div class="stars-layer stars-medium"></div>
        <div class="stars-layer stars-large"></div>
    </div>

    <div class="floater" style="top:18%; width:34px; height:34px; animation-duration: 22s; animation-delay: -4s;">
        <svg width="34" height="34" viewBox="0 0 34 34" style="animation: tumble 11s ease-in-out infinite;">
            <ellipse cx="17" cy="20" rx="8" ry="10" fill="#e5e7eb"/>
            <circle cx="17" cy="10" r="8" fill="#f5f5f7"/>
            <circle cx="17" cy="10" r="5.5" fill="#7c5cff" opacity="0.55"/>
            <rect x="4" y="17" width="6" height="3" rx="1.5" fill="#cbd5e1"/>
            <rect x="24" y="17" width="6" height="3" rx="1.5" fill="#cbd5e1"/>
        </svg>
    </div>
    <div class="floater" style="top:62%; width:30px; height:30px; animation-duration: 27s; animation-delay: -14s;">
        <svg width="30" height="30" viewBox="0 0 34 34" style="animation: tumble 9s ease-in-out infinite;">
            <ellipse cx="17" cy="20" rx="8" ry="10" fill="#e5e7eb"/>
            <circle cx="17" cy="10" r="8" fill="#f5f5f7"/>
            <circle cx="17" cy="10" r="5.5" fill="#7c5cff" opacity="0.55"/>
            <rect x="4" y="17" width="6" height="3" rx="1.5" fill="#cbd5e1"/>
            <rect x="24" y="17" width="6" height="3" rx="1.5" fill="#cbd5e1"/>
        </svg>
    </div>

    <div class="floater planet" style="top:10%; width:28px; height:28px; background:#7c5cff; box-shadow: inset -7px -6px 0 rgba(0,0,0,0.25), 0 0 12px rgba(255,255,255,0.15); animation-duration: 30s; animation-delay: -8s;"></div>
    <div class="floater planet" style="top:40%; width:20px; height:20px; background:#38bdf8; box-shadow: inset -5px -4px 0 rgba(0,0,0,0.25), 0 0 8px rgba(255,255,255,0.15); animation-duration: 24s; animation-delay: -2s;"></div>
    <div class="floater planet" style="top:75%; width:34px; height:34px; background:#f472b6; box-shadow: inset -8px -7px 0 rgba(0,0,0,0.25), 0 0 14px rgba(255,255,255,0.15); animation-duration: 34s; animation-delay: -20s;"></div>
    <div class="floater planet" style="top:88%; width:22px; height:22px; background:#fb923c; box-shadow: inset -5px -5px 0 rgba(0,0,0,0.25), 0 0 9px rgba(255,255,255,0.15); animation-duration: 20s; animation-delay: -6s;"></div>
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
# واجهة الإدخال
# ----------------------------------------------------------------------------
with st.form("video_form"):
    prompt = st.text_area(
        "وصف الفيديو (Prompt)",
        placeholder="مثال: رائد فضاء يمشي ببطء على سطح القمر، غبار ناعم يتطاير حول قدميه، إضاءة سينمائية...",
        height=130,
    )

    duration = st.slider(
        "مدة الفيديو (بالثواني)",
        min_value=MIN_DURATION,
        max_value=MAX_DURATION,
        value=DEFAULT_DURATION,
        step=1,
    )

    with st.expander("⚙️ إعدادات متقدمة"):
        enhance_prompt = st.checkbox("تحسين الوصف تلقائيًا (Enhance Prompt)", value=True)
        high_resolution = st.checkbox("دقة عالية (أبطأ في التوليد)", value=False)

    submitted = st.form_submit_button("🎬 إنشاء الفيديو")

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
                    enhance_prompt=enhance_prompt,
                    high_resolution=high_resolution,
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
