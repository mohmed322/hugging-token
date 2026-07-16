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
"""

import os
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
# التنسيق (CSS) — ثيم أبيض مينيمال بلمسة بنفسجية
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    :root {
        --bg: #ffffff;
        --text-primary: #0f0f10;
        --text-secondary: #6b7280;
        --accent: #7c5cff;
        --card-bg: #f6f6f8;
        --card-border: #ececf0;
        --button-bg: #111114;
        --button-text: #ffffff;
    }

    .stApp { background: var(--bg) !important; }
    .block-container { max-width: 720px; margin: 0 auto; padding-top: 2.5rem !important; }

    h1, h2, h3, p, label, span, div { color: var(--text-primary); }

    .app-header {
        text-align: center;
        margin-bottom: 1.8rem;
    }
    .app-header h1 {
        font-size: 2rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
    }
    .app-header p {
        color: var(--text-secondary) !important;
        font-size: 0.95rem;
    }
    .app-badge {
        display: inline-block;
        background: linear-gradient(135deg, var(--accent), #a78bfa);
        color: #fff !important;
        padding: 4px 14px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
    }

    div[data-testid="stForm"] {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 20px;
        padding: 1.6rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05);
    }

    div[data-testid="stForm"] textarea {
        border-radius: 12px !important;
        direction: auto !important;
        unicode-bidi: plaintext !important;
        text-align: start !important;
    }

    .stButton button, div[data-testid="stForm"] button[kind="primary"] {
        background-color: var(--button-bg) !important;
        color: var(--button-text) !important;
        border-radius: 999px !important;
        font-weight: 700 !important;
        padding: 0.6rem 1.4rem !important;
        border: none !important;
        width: 100%;
    }

    .stDownloadButton button {
        background-color: var(--accent) !important;
        color: #fff !important;
        border-radius: 999px !important;
        font-weight: 700 !important;
        border: none !important;
        width: 100%;
    }
    </style>
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
    try:
        result = client.predict(
            None,              # الصورة الاختيارية لتوجيه الحركة — مش مستخدمة هنا
            prompt,            # وصف الفيديو (Prompt)
            duration,          # المدة بالثواني
            enhance_prompt,    # تحسين الوصف تلقائيًا
            high_resolution,   # دقة عالية (أبطأ في التوليد)
            api_name="/generate",
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
