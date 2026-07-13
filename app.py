"""
مساعد ذكاء اصطناعي عام — نسخة شات (تصميم أبيض مينيمال)
تطبيق Streamlit فيه شات ذكاء اصطناعي بيرد على أي سؤال، وبيقدر كمان يولّد:
- صورة واحدة بستايل 3D Pixar/Disney (Hugging Face — FLUX.1-schnell)
- فيديو Shorts قصير كامل: سيناريو (Hugging Face — Qwen2.5) + تعليق صوتي عربي (gTTS)
  + مشاهد بستايل 3D Pixar/Disney + مونتاج (MoviePy)
كل ده بيتحدد تلقائيًا من نية المستخدم في رسالته، من غير ما يحتاج يختار وضع معيّن.

أول ما تدخل الموقع: مفيش غير بوكس واحد أبيض شكل "pill" في النص، من غير أي كلام تاني.
تكتب أي حاجة، تدوس إرسال، وبعدين الشات يتحول لوضع محادثة عادي (البوكس يفضل ثابت تحت).
"""

import os
import re
import json
import time
import tempfile
import traceback

import requests
import streamlit as st
import streamlit.components.v1 as components
from gtts import gTTS

# ----------------------------------------------------------------------------
# إصلاح توافق: Pillow (10+) شالت الاسم القديم Image.ANTIALIAS واستبدلته بـ
# Image.LANCZOS، لكن نسخة MoviePy القديمة لسه بتنادي على الاسم القديم في
# دالة resize، فبيطلع خطأ "module 'PIL.Image' has no attribute 'ANTIALIAS'".
# الحل: نرجّع الاسم القديم كـ alias قبل ما MoviePy يستخدمه.
# ----------------------------------------------------------------------------
from PIL import Image as _PILImage
if not hasattr(_PILImage, "ANTIALIAS"):
    _PILImage.ANTIALIAS = _PILImage.LANCZOS

from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    ColorClip,
)

# ----------------------------------------------------------------------------
# إعدادات عامة
# ----------------------------------------------------------------------------
TARGET_W, TARGET_H = 1080, 1920  # مقاس 9:16 المناسب لـ Shorts/Reels
st.set_page_config(page_title="مساعد الذكاء الاصطناعي", layout="centered")

# ----------------------------------------------------------------------------
# التنسيق (CSS) - ثيم أبيض مينيمال مقتبس من تصميم الموقع المرجعي
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ---------- إخفاء شريط Streamlit العلوي بالكامل (Deploy / القائمة / الفوتر) ---------- */
    header[data-testid="stHeader"] { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    /* ---------- ألوان الثيم الأبيض المقتبسة من التصميم المرجعي ---------- */
    :root {
        --bg: #ffffff;
        --text-primary: #0f0f10;
        --text-secondary: #6b7280;
        --accent: #7c5cff;
        --pill-bg: #ffffff;
        --pill-border: #e6e6ea;
        --button-bg: #111114;
        --button-text: #ffffff;
        --bubble-bg: #f6f6f8;
        --bubble-border: #ececf0;
    }

    .stApp {
        background: var(--bg) !important;
    }
    h1, h2, h3, h4, p, label, span, div {
        color: var(--text-primary) !important;
    }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
        color: var(--text-secondary) !important;
    }

    .block-container {
        max-width: 700px;
        margin: 0 auto;
        padding-top: 3rem !important;
    }

    /* ---------- فقاعات الشات ---------- */
    [data-testid="stChatMessage"] {
        background-color: var(--bubble-bg);
        border-radius: 18px;
        border: 1px solid var(--bubble-border);
        padding: 6px 10px;
        margin-bottom: 10px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }

    /* ---------- صندوق الشات الثابت تحت (وضع المحادثة) ---------- */
    [data-testid="stChatInput"] {
        background: var(--pill-bg) !important;
        border-radius: 26px !important;
        border: 1px solid var(--pill-border) !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.07) !important;
        max-width: 700px;
        margin: 0 auto;
    }
    [data-testid="stChatInput"] textarea {
        color: var(--text-primary) !important;
        resize: none !important;
        overflow-y: auto !important;
        max-height: 260px !important;
        transition: height 0.05s ease-out;
    }
    [data-testid="stChatInput"] button {
        background-color: var(--button-bg) !important;
        border-radius: 9999px !important;
    }
    [data-testid="stChatInput"] button svg {
        fill: var(--button-text) !important;
    }
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
    }
    /* Streamlit بيحط لون تركيز (focus) أحمر افتراضي على الحقول — بنلغيه عشان
       البوكس يفضل بنفس شكل الثيم الأبيض/الأسود حتى وهو متفوكس أو بعد إرسال رسالة */
    [data-testid="stChatInput"]:focus-within,
    [data-testid="stChatInput"] textarea:focus,
    [data-testid="stChatInput"] textarea:focus-visible,
    div[data-testid="stForm"]:focus-within,
    div[data-testid="stForm"] textarea:focus,
    div[data-testid="stForm"] textarea:focus-visible {
        outline: none !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.07) !important;
        border-color: var(--pill-border) !important;
    }
    [data-testid="stChatInput"] textarea,
    div[data-testid="stForm"] textarea {
        outline: none !important;
        box-shadow: none !important;
    }

    /* ---------- دعم خلط العربي والإنجليزي جوه نفس الرسالة/البوكس من غير ما
       الكلام يترتب بالمقلوب (مشكلة bidi الكلاسيكية) ---------- */
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] div,
    [data-testid="stChatInput"] textarea,
    div[data-testid="stForm"] textarea {
        direction: auto !important;
        unicode-bidi: plaintext !important;
        text-align: start !important;
    }

    /* ---------- بوكس الهبوط (Landing) اللي بيبان أول ما تدخل الموقع ---------- */
    .landing-shell {
        min-height: 62vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    div[data-testid="stForm"] {
        background: var(--pill-bg);
        border: 1px solid var(--pill-border);
        border-radius: 26px;
        box-shadow: 0 14px 40px rgba(0, 0, 0, 0.08);
        padding: 8px 8px 8px 26px;
        width: 100%;
    }
    div[data-testid="stForm"] div[data-testid="stVerticalBlockBorderWrapper"] > div,
    div[data-testid="stForm"] div[data-testid="stVerticalBlock"] {
        gap: 0 !important;
    }
    div[data-testid="stForm"] [data-baseweb="base-input"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stForm"] input,
    div[data-testid="stForm"] textarea {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: var(--text-primary) !important;
        font-size: 16px !important;
    }
    div[data-testid="stForm"] textarea {
        resize: none !important;
        overflow-y: auto !important;
        min-height: 46px !important;
        max-height: 260px !important;
        line-height: 1.5 !important;
        padding-top: 12px !important;
        padding-bottom: 12px !important;
        transition: height 0.05s ease-out;
    }
    div[data-testid="stForm"] button {
        background-color: var(--button-bg) !important;
        color: var(--button-text) !important;
        border-radius: 9999px !important;
        border: none !important;
        width: 46px;
        height: 46px;
        min-height: 46px;
        padding: 0 !important;
        font-weight: 700;
        flex-shrink: 0;
    }
    div[data-testid="stForm"] button:hover {
        transform: scale(1.04);
    }
    /* لازم لون نص/سهم زرار الإرسال يبقى أبيض دايمًا، حتى لو القواعد العامة
       (h1,h2,h3,h4,p,label,span,div) بتحاول تلوّنه بالأسود بعدها */
    div[data-testid="stForm"] button,
    div[data-testid="stForm"] button p,
    div[data-testid="stForm"] button span,
    div[data-testid="stForm"] button div {
        color: var(--button-text) !important;
    }
    [data-testid="stChatInput"] button,
    [data-testid="stChatInput"] button p,
    [data-testid="stChatInput"] button span,
    [data-testid="stChatInput"] button div {
        color: var(--button-text) !important;
    }
    /* الفورم نفسه يترص أفقي: الحقل والزرار جنب بعض، والزرار يفضل تحت لما البوكس يكبر */
    div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] {
        align-items: flex-end !important;
        gap: 4px !important;
    }
    div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] > div:last-child {
        padding-bottom: 4px;
    }

    /* ---------- إخفاء أيقونة/مكعب الأفاتار اللي بيظهر قبل كل رسالة ---------- */
    [data-testid="stChatMessage"] [data-testid*="Avatar"] {
        display: none !important;
    }
    [data-testid="stChatMessage"] {
        gap: 0 !important;
    }

    div[data-testid="stExpander"] {
        background-color: var(--bubble-bg);
        border-radius: 16px;
        border: 1px solid var(--bubble-border);
    }
    div[data-testid="stStatusWidget"] {
        background-color: var(--bubble-bg) !important;
        border-radius: 16px !important;
        border: 1px solid var(--bubble-border) !important;
    }
    .stButton button {
        background-color: var(--button-bg) !important;
        color: var(--button-text) !important;
        border-radius: 9999px !important;
        border: none !important;
        padding: 10px 22px !important;
        font-weight: 600 !important;
    }
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-thumb { background: #d8d8de; border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# سكريبت صغير بيخلي بوكس الكتابة (سواء بوكس الهبوط أو بوكس الشات تحت) يكبر
# لوحده تلقائيًا مع زيادة الكلام اللي بيتكتب فيه، بدل ما يفضل سطر واحد ثابت.
# ----------------------------------------------------------------------------
components.html(
    """
    <script>
    (function () {
        const MAX_HEIGHT = 260; // أقصى ارتفاع بالبكسل قبل ما يبدأ سكرول جوه البوكس

        function autoResize(ta) {
            ta.style.height = "auto";
            const newHeight = Math.min(ta.scrollHeight, MAX_HEIGHT);
            ta.style.height = newHeight + "px";
        }

        function bindAll() {
            const doc = window.parent.document;
            const selectors = [
                'div[data-testid="stForm"] textarea',
                '[data-testid="stChatInput"] textarea',
            ];
            doc.querySelectorAll(selectors.join(",")).forEach((ta) => {
                ta.setAttribute("dir", "auto");
                if (ta.dataset.autoGrowBound) return;
                ta.dataset.autoGrowBound = "true";
                ta.addEventListener("input", () => autoResize(ta));
                autoResize(ta);
            });
        }

        // الصفحة عند Streamlit بتتجدد باستمرار، فبنعيد الفحص كل شوية عشان
        // نمسك أي بوكس جديد يتولد بعد rerun
        setInterval(bindAll, 400);
        bindAll();
    })();
    </script>
    """,
    height=0,
)

# ----------------------------------------------------------------------------
# مفتاح الـ API — بتتقرا من إعدادات السيرفر (secrets) مش من الزائر
# ----------------------------------------------------------------------------
# توكن Hugging Face (Inference API) — حط التوكن بتاعك هنا بسهولة
HF_TOKEN = "ضع التوكن هنا"
# لو مش عايز تكتب التوكن جوه الكود، سيبه زي ما هو وحط قيمته في secrets/متغير بيئة
# باسم HF_TOKEN، وهيتقرا تلقائيًا من هناك كخيار احتياطي.
if HF_TOKEN == "ضع التوكن هنا":
    HF_TOKEN = st.secrets.get("HF_TOKEN", os.environ.get("HF_TOKEN", ""))

# موديل الرسم على Hugging Face Inference API (مجاني ومفتوح المصدر وسريع)
HF_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"
# ملحوظة: Hugging Face ألغت الدومين القديم api-inference.huggingface.co ونقلت كل
# استدعاءات الـ Inference (نصوص وصور) لدومين موحّد واحد: router.huggingface.co
HF_IMAGE_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_IMAGE_MODEL}"
# ذيل ثابت بيتضاف لأي وصف رسم عشان نضمن ستايل الكرتون 3D دايمًا
HF_STYLE_SUFFIX = "3D Pixar Disney style animation, vibrant colors, cute character, high quality"

# موديل كتابة النصوص (السيناريو + فهم النية + الشات) على Hugging Face
HF_TEXT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
HF_CHAT_API_URL = "https://router.huggingface.co/v1/chat/completions"

if not HF_TOKEN:
    st.error(
        "مفتاح HF_TOKEN (Hugging Face) مش موجود. حط قيمته في متغير HF_TOKEN في أول الكود، "
        "أو في إعدادات السيرفر (secrets) باسم HF_TOKEN."
    )
    st.stop()

# ----------------------------------------------------------------------------
# حماية بسيطة من الاستخدام المبالغ فيه (كل الصور والفيديوهات بتتعمل على حسابك أنت)
# ----------------------------------------------------------------------------
MAX_GENERATIONS_PER_SESSION = 6  # عدّل الرقم ده حسب ميزانيتك لتكلفة الـ API (صور + فيديوهات مع بعض)

if "generations_made" not in st.session_state:
    st.session_state.generations_made = 0

if "messages" not in st.session_state:
    st.session_state.messages = []  # فاضية تمامًا لحد ما المستخدم يبعت أول رسالة

# ----------------------------------------------------------------------------
# دوال الذكاء الاصطناعي
# ----------------------------------------------------------------------------

def _extract_json(raw_text: str) -> dict:
    """موديلات الشات المفتوحة أحيانًا بتلف الـ JSON جوه ```json ...``` أو بتضيف
    كلام قبله/بعده، فالدالة دي بتدور على أول { وآخر } وتحاول تقرأ اللي بينهم."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise json.JSONDecodeError("مفيش JSON في الرد", text, 0)
    return json.loads(text[start:end + 1])


def hf_chat_completion(messages, hf_token: str, max_tokens: int = 700, temperature: float = 0.7) -> str:
    """بينادي على موديل نصوص مجاني على Hugging Face (Qwen2.5-Instruct) عن طريق
    الـ Chat Completions API، ويرجع نص الرد."""
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": HF_TEXT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    max_retries = 4
    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                HF_CHAT_API_URL, headers=headers, json=payload, timeout=90
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()

            if response.status_code == 503:
                wait_s = 5
                try:
                    wait_s = response.json().get("estimated_time", 5)
                except Exception:
                    pass
                time.sleep(min(wait_s, 20))
                continue

            last_error = f"كود {response.status_code}: {response.text[:200]}"
        except Exception as e:
            last_error = str(e)

    raise RuntimeError(f"HuggingFace: فشل استدعاء موديل النصوص — {last_error}")


def classify_intent(user_text: str, hf_token: str) -> dict:
    """يفهم من كلام المستخدم هل عايز صورة واحدة، فيديو قصير، أو مجرد كلام/سؤال عادي."""
    system_prompt = (
        "أنت مساعد ذكاء اصطناعي عام قادر على الشات، وتوليد صور، وتوليد فيديوهات Shorts قصيرة. "
        "افهم نية المستخدم من رسالته، ولازم ترجع JSON فقط بدون أي نص إضافي ولا أي شرح ولا "
        "Markdown، بالشكل ده بالظبط:\n"
        '{"intent": "video" | "image" | "chat", "topic": "..."}\n'
        "- \"video\": لو طالب إنتاج فيديو Shorts قصير بسيناريو ومشاهد متحركة.\n"
        "- \"image\": لو طالب رسم/توليد صورة واحدة بس (مش فيديو).\n"
        "- \"chat\": في أي حالة تانية — دردشة، سؤال، طلب مساعدة أو حل لأي موضوع.\n"
        "topic: وصف مختصر وواضح لموضوع الصورة أو الفيديو المطلوب لو النية video أو image، "
        "أو نص فاضي لو chat."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f'الرسالة: "{user_text}"'},
    ]
    try:
        raw = hf_chat_completion(messages, hf_token, max_tokens=200, temperature=0.2)
        data = _extract_json(raw)
        intent = data.get("intent", "chat")
        if intent not in ("video", "image", "chat"):
            intent = "chat"
        return {"intent": intent, "topic": (data.get("topic") or "").strip()}
    except Exception:
        return {"intent": "chat", "topic": ""}


def chat_reply(history, user_text: str, hf_token: str) -> str:
    """رد شات طبيعي ومفيد بالعربي على أي موضوع، مع أخذ آخر رسائل المحادثة في الاعتبار."""
    convo_lines = []
    for m in history[-8:]:
        if m.get("type") == "text":
            speaker = "المستخدم" if m["role"] == "user" else "أنت (المساعد)"
            convo_lines.append(f"{speaker}: {m['content']}")
    convo_text = "\n".join(convo_lines)

    system_prompt = (
        "أنت مساعد ذكاء اصطناعي عام على أعلى مستوى من الذكاء والطلاقة، بنفس مستوى "
        "ChatGPT في جودة الفهم والرد. اتبع القواعد دي بدقة:\n\n"
        "1) اللغة: رد بنفس اللغة اللي كتب بيها المستخدم بالظبط. لو كتب بالعربي (فصحى أو "
        "عامية مصرية) رد بعامية مصرية واضحة وطبيعية وذكية، مش ركيكة ومش مترجمة حرفيًا. "
        "لو كتب بالإنجليزي رد بإنجليزي فصيح وطبيعي كأنك متحدث أصلي. لو خلط اللغتين في "
        "جملته، رد بنفس الخلطة اللي هو مرتاح ليها. متتكلمش بلغة تالتة أبدًا إلا لو طلب "
        "صراحة.\n\n"
        "2) الذكاء والعمق: افهم السؤال أو الطلب بعمق قبل ما ترد — متردّش برد سطحي أو "
        "عام. لو السؤال معقد أو فيه أكتر من جزء، فكّر في كل جزء وجاوب عليه بالكامل. "
        "لو محتاج معلومة دقيقة (أرقام، خطوات، كود، تواريخ)، اديها بدقة ومن غير تخمين. "
        "لو مش متأكد من حاجة، قول كده بصراحة بدل ما تختلق إجابة.\n\n"
        "3) الأسلوب: اتكلم بثقة وطبيعية زي إنسان خبير بيشرح لصاحبه، مش زي روبوت بيقرأ "
        "من كتيب. استخدم أمثلة أو تشبيهات لو هتوضح الفكرة. رتّب الرد بفقرات أو نقاط لو "
        "المحتوى طويل أو فيه خطوات، وخليه نص عادي مباشر لو السؤال بسيط.\n\n"
        "4) الطول: خلي ردك بالطول اللي الموضوع يستاهله فعلاً — لو السؤال بسيط رد مختصر "
        "ومفيد، ولو محتاج شرح فصّل وما تبخلش، بس من غير حشو أو تكرار.\n\n"
        "5) الاستمرارية: خد بالك من سياق المحادثة اللي فاتت وابني عليه، ومتكررش نفس "
        "الكلام اللي قلته قبل كده.\n\n"
        "6) لو حسيت إن المستخدم محتاج صورة أو فيديو بالذكاء الاصطناعي (مثلاً بيوصف مشهد "
        "أو فكرة بصرية)، اقترح عليه إن الموقع يقدر يولّدها له لو طلب بوضوح، من غير ما "
        "تفتعل الاقتراح ده في كل رد."
    )
    user_content = (
        f"المحادثة السابقة:\n{convo_text}\n\n"
        f"رسالة المستخدم الجديدة: \"{user_text}\"\n\n"
        "ردك (بنفس لغة المستخدم، ذكي، دقيق، وطبيعي):"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return hf_chat_completion(messages, hf_token, max_tokens=1400, temperature=0.6)


def generate_image_visual_prompt(idea: str, hf_token: str) -> str:
    """يحوّل طلب المستخدم (بأي لغة) لوصف بصري دقيق بالإنجليزية لصورة واحدة."""
    system_prompt = (
        "أنت مخرج فني ومصمم مشاهد محترف متخصص في وصف صور بدقة عالية جدًا عشان تتولد "
        "بالذكاء الاصطناعي (image generation prompt engineering) بستايل كرتون 3D "
        "Pixar/Disney. اقرأ طلب المستخدم (ممكن يكون عربي أو إنجليزي) وافهم بالظبط "
        "الفكرة والمشاعر والتفاصيل اللي هو محتاجها، حتى لو مكتوبة باختصار أو غموض.\n\n"
        "اكتب وصف بصري واحد بالإنجليزية، غني ودقيق ومحدد وليس عام أو تافه، يغطي:\n"
        "- الشخصية/الشخصيات الرئيسية بالتفصيل: الشكل، التعبير، الوضعية، الملابس.\n"
        "- المكان والخلفية بالتفصيل (بيئة، عناصر محيطة، عمق المشهد).\n"
        "- الإضاءة ونوعها واتجاهها (مثلاً golden hour lighting, soft rim light).\n"
        "- زاوية الكاميرا والتكوين (مثلاً close-up, wide shot, dynamic angle).\n"
        "- الألوان السائدة والمزاج العام للمشهد.\n\n"
        "اكتب النتيجة في سطر أو سطرين بحد أقصى، جمل وصفية مترابطة مفصولة بفواصل "
        "(comma-separated descriptive phrases)، من غير أي مقدمة أو شرح أو علامات "
        "اقتباس أو تفسير — الوصف نفسه بس."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f'الطلب: "{idea}"'},
    ]
    return hf_chat_completion(messages, hf_token, max_tokens=220, temperature=0.75).strip()


def generate_script(idea: str, hf_token: str) -> dict:
    """يستدعي موديل النصوص على Hugging Face ويرجع سيناريو مقسم لمشاهد بصيغة JSON،
    بما فيه وصف رسم لكل مشهد."""
    system_prompt = (
        "أنت كاتب سيناريو محترف لفيديوهات Shorts/Reels قصيرة (60 ثانية تقريباً)، وفي نفس الوقت "
        "مخرج فني بيوصف كل مشهد عشان يتحول لصورة بالذكاء الاصطناعي بستايل كرتون 3D Pixar/Disney. "
        "لازم ترجع JSON فقط بدون أي نص إضافي ولا Markdown، بالشكل ده بالظبط:\n"
        '{"title": "...", "scenes": [{"narration": "...", "image_prompt": "..."}, ...]}\n'
        "قسّم السيناريو إلى 5 إلى 6 مشاهد قصيرة متتابعة تحكي قصة أو تشرح الفكرة بشكل جذاب.\n"
        "لكل مشهد اكتب:\n"
        "- narration: جملة أو جملتين للتعليق الصوتي بالعربية الفصحى المبسطة (بدون رموز أو علامات غريبة).\n"
        "- image_prompt: وصف بصري غني ودقيق ومفصّل بالإنجليزية (comma-separated "
        "descriptive phrases) يغطي: الشخصية وتعبيرها ووضعيتها، المكان والخلفية، "
        "الإضاءة، زاوية الكاميرا/التكوين، والمزاج العام — مش وصف عام أو سطحي، لازم يكون "
        'محدد وقابل للتخيل بوضوح. لازم ينتهي دايمًا بالكلمات دي بالظبط: '
        '"3D Pixar Disney style animation, vibrant colors, cute character, high quality"'
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f'الفكرة: "{idea}"'},
    ]
    raw = hf_chat_completion(messages, hf_token, max_tokens=1200, temperature=0.8)
    return _extract_json(raw)


def text_to_speech(text: str, out_path: str) -> str:
    """يحول نص عربي إلى ملف صوتي mp3."""
    tts = gTTS(text=text, lang="ar")
    tts.save(out_path)
    return out_path


def _log_debug(debug_log, message: str):
    if debug_log is not None:
        debug_log.append(message)
    print(f"[DEBUG] {message}")


def generate_scene_image(image_prompt: str, out_path: str, hf_token: str, debug_log=None) -> bool:
    """بيولّد صورة المشهد بستايل 3D Pixar/Disney عن طريق Hugging Face Inference API
    (موديل FLUX.1-schnell)، ويحفظها في out_path."""

    # نضمن إن ستايل الكرتون 3D يتضاف دايمًا للوصف، حتى لو الوصف الجاي من موديل السيناريو
    # ناسي يحطه أو حاطه بصيغة مختلفة
    full_prompt = image_prompt.strip()
    if HF_STYLE_SUFFIX.lower() not in full_prompt.lower():
        full_prompt = f"{full_prompt}, {HF_STYLE_SUFFIX}"

    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Accept": "image/png",
    }
    payload = {
        "inputs": full_prompt,
        "parameters": {
            # أقرب أبعاد لمقاس 9:16 (لازم تبقى من مضاعفات 8 لموديلات الرسم)
            "width": 768,
            "height": 1344,
        },
        "options": {
            # ننتظر لو الموديل لسه بيتحمّل بدل ما نرجع فشل على طول
            "wait_for_model": True,
        },
    }

    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = requests.post(
                HF_IMAGE_API_URL, headers=headers, json=payload, timeout=120
            )

            if response.status_code == 200 and response.headers.get(
                "content-type", ""
            ).startswith("image/"):
                with open(out_path, "wb") as f:
                    f.write(response.content)
                return True

            # الموديل لسه بيتحمّل على سيرفرات Hugging Face — ننتظر شوية ونعيد المحاولة
            if response.status_code == 503:
                wait_s = 5
                try:
                    wait_s = response.json().get("estimated_time", 5)
                except Exception:
                    pass
                _log_debug(
                    debug_log,
                    f"HuggingFace: الموديل لسه بيتحمّل، هننتظر {wait_s:.0f} ثانية ونعيد المحاولة "
                    f"(محاولة {attempt + 1}/{max_retries})...",
                )
                time.sleep(min(wait_s, 20))
                continue

            _log_debug(
                debug_log,
                f"HuggingFace: فشل توليد الصورة — كود {response.status_code}: {response.text[:200]}",
            )
            return False

        except Exception as e:
            _log_debug(debug_log, f"HuggingFace: استثناء أثناء توليد الصورة — {e}")
            return False

    _log_debug(debug_log, "HuggingFace: الموديل فضل بيتحمّل بعد كل المحاولات، هنستخدم خلفية احتياطية.")
    return False


def cover_crop(clip, target_w=TARGET_W, target_h=TARGET_H):
    """يكبر المقطع ليغطي المقاس المطلوب 9:16 ثم يوسّطه (crop تلقائي)."""
    w, h = clip.size
    scale = max(target_w / w, target_h / h)
    clip = clip.resize(scale).set_position("center")
    return CompositeVideoClip([clip], size=(target_w, target_h))


def make_fallback_clip(duration, color=(240, 240, 243)):
    """خلفية فاتحة احتياطية لو فشل توليد صورة المشهد."""
    return ColorClip(size=(TARGET_W, TARGET_H), color=color, duration=duration)


def build_generated_scene(image_prompt, audio_path, duration, hf_token, tmp_dir, idx, debug_log=None):
    """بيولّد صورة المشهد بالذكاء الاصطناعي (Hugging Face) ويحولها لمشهد فيديو بتأثير Ken Burns."""
    img_tmp = os.path.join(tmp_dir, f"img_{idx}.png")
    ok = generate_scene_image(image_prompt, img_tmp, hf_token, debug_log)
    audio_clip = AudioFileClip(audio_path)

    if ok:
        try:
            img_clip = ImageClip(img_tmp).set_duration(duration)
            covered = cover_crop(img_clip)
            # تأثير Ken Burns: تكبير بطيء ومتصاعد
            zoomed = covered.resize(lambda t: 1 + 0.06 * (t / duration))
            zoomed = zoomed.set_position("center")
            scene = CompositeVideoClip([zoomed], size=(TARGET_W, TARGET_H)).set_duration(duration).set_audio(audio_clip)
            return scene
        except Exception as e:
            _log_debug(debug_log, f"مشهد {idx + 1}: الصورة اتولدت لكن MoviePy فشل يقراها/يعالجها — {e}")

    return make_fallback_clip(duration).set_audio(audio_clip)


def build_final_video(scenes_data, hf_token, tmp_dir, progress_callback=None, debug_log=None):
    clips = []
    for idx, scene in enumerate(scenes_data):
        audio_path = os.path.join(tmp_dir, f"audio_{idx}.mp3")
        text_to_speech(scene["narration"], audio_path)
        duration = AudioFileClip(audio_path).duration

        clip = build_generated_scene(scene["image_prompt"], audio_path, duration, hf_token, tmp_dir, idx, debug_log)

        clips.append(clip)
        if progress_callback:
            progress_callback((idx + 1) / len(scenes_data))

    final = concatenate_videoclips(clips, method="compose")
    out_path = os.path.join(tmp_dir, "final_output.mp4")
    final.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", threads=4, verbose=False, logger=None)
    return out_path


def render_scenes_markdown(scenes):
    lines = []
    for i, sc in enumerate(scenes, start=1):
        lines.append(f"**مشهد {i}:** {sc['narration']}  \n*(رسم: {sc['image_prompt']})*")
    return "\n\n".join(lines)


def run_video_pipeline(idea: str, status):
    """بيبني الفيديو كامل مع تحديث مؤشر التفكير خطوة بخطوة، ويرجع dict للرسالة النهائية."""
    tmp_dir = tempfile.mkdtemp()
    status.update(label="جاري كتابة السيناريو...")
    script_data = generate_script(idea, HF_TOKEN)

    scenes_md = render_scenes_markdown(script_data["scenes"])
    status.write(f"**{script_data.get('title', 'السيناريو')}**")
    status.write(scenes_md)

    debug_log = []

    def _update(p):
        status.update(label=f"جاري رسم المشاهد بستايل 3D Pixar... {int(p * 100)}%")

    status.update(label="جاري رسم المشاهد بستايل 3D Pixar...")
    final_path = build_final_video(
        script_data["scenes"], HF_TOKEN, tmp_dir,
        progress_callback=_update, debug_log=debug_log,
    )
    status.update(label="تم إنتاج الفيديو بنجاح!", state="complete")

    return {
        "role": "assistant",
        "type": "video",
        "content": final_path,
        "title": script_data.get("title", "الفيديو"),
        "scenes_md": scenes_md,
        "debug_log": debug_log,
    }


def run_image_pipeline(idea: str, status):
    """بيولّد صورة واحدة بس بالذكاء الاصطناعي (مش فيديو)، ويرجع dict للرسالة النهائية."""
    tmp_dir = tempfile.mkdtemp()
    debug_log = []

    status.update(label="جاري تجهيز وصف الصورة...")
    visual_prompt = generate_image_visual_prompt(idea, HF_TOKEN)

    status.update(label="جاري رسم الصورة بستايل 3D Pixar...")
    img_path = os.path.join(tmp_dir, "single_image.png")
    ok = generate_scene_image(visual_prompt, img_path, HF_TOKEN, debug_log)

    if ok:
        status.update(label="تم رسم الصورة بنجاح!", state="complete")
    else:
        status.update(label="حصلت مشكلة أثناء رسم الصورة", state="error")

    return {
        "role": "assistant",
        "type": "image",
        "content": img_path if ok else None,
        "debug_log": debug_log,
    }


def render_assistant_message(msg, key_suffix):
    """يعرض رسالة الفيديو/الصورة/النص بنفس الشكل سواء وقت التوليد أو من السجل."""
    if msg["type"] == "text":
        st.markdown(msg["content"])
        return

    if msg["type"] == "image":
        if msg.get("content") and os.path.exists(msg["content"]):
            st.image(msg["content"])
            with open(msg["content"], "rb") as f:
                st.download_button(
                    "تحميل الصورة",
                    data=f.read(),
                    file_name="ai_image.png",
                    mime="image/png",
                    key=f"dlimg_{key_suffix}",
                )
        else:
            st.warning("تعذّر توليد الصورة، أو انتهت صلاحيتها من الذاكرة المؤقتة. حاول تاني.")
        if msg.get("debug_log"):
            with st.expander("حصلت مشكلة أثناء الرسم — اضغط هنا للتفاصيل"):
                for line in msg["debug_log"]:
                    st.caption(f"• {line}")
        return

    if msg.get("title"):
        st.markdown(f"**{msg['title']}**")
    if msg.get("scenes_md"):
        with st.expander("عرض السيناريو"):
            st.markdown(msg["scenes_md"])
    if os.path.exists(msg["content"]):
        st.video(msg["content"])
        with open(msg["content"], "rb") as f:
            st.download_button(
                "تحميل الفيديو",
                data=f.read(),
                file_name="short_video.mp4",
                mime="video/mp4",
                key=f"dl_{key_suffix}",
            )
    else:
        st.warning("انتهت صلاحية هذا الفيديو من الذاكرة المؤقتة.")
    if msg.get("debug_log"):
        with st.expander("بعض المشاهد استخدمت خلفية احتياطية — اضغط هنا للتفاصيل"):
            for line in msg["debug_log"]:
                st.caption(f"• {line}")


if "pending" not in st.session_state:
    st.session_state.pending = False


def queue_user_message(user_text: str):
    """بيضيف رسالة المستخدم وبس، ويعلّم إن فيه رد لازم يتولّد. الرد نفسه بيتولد
    في المسار الموحّد تحت (بعد إعادة التشغيل) عشان الشكل يبقى مضبوط من أول لحظة
    من غير أي وميض أو ترتيب غلط."""
    st.session_state.messages.append({"role": "user", "type": "text", "content": user_text})
    st.session_state.pending = True


def generate_reply():
    """بيتولّد الرد على آخر رسالة مستخدم، وبيتعرض في مكانه الصحيح جوه المحادثة."""
    user_text = st.session_state.messages[-1]["content"]
    remaining = MAX_GENERATIONS_PER_SESSION - st.session_state.generations_made

    with st.chat_message("assistant"):
        with st.status("بيفكر...", expanded=True) as status:
            try:
                result = classify_intent(user_text, HF_TOKEN)
                intent = result["intent"]
                topic = result["topic"] or user_text

                if intent == "video":
                    if remaining <= 0:
                        status.update(label="وصلت للحد الأقصى", state="error")
                        reply = "وصلت للحد الأقصى من الصور/الفيديوهات المجانية في هذه الجلسة. حدّث الصفحة لاحقاً أو تواصل معنا للمزيد."
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "type": "text", "content": reply})
                    else:
                        assistant_msg = run_video_pipeline(topic, status)
                        st.session_state.generations_made += 1
                        render_assistant_message(assistant_msg, key_suffix="new")
                        st.session_state.messages.append(assistant_msg)

                elif intent == "image":
                    if remaining <= 0:
                        status.update(label="وصلت للحد الأقصى", state="error")
                        reply = "وصلت للحد الأقصى من الصور/الفيديوهات المجانية في هذه الجلسة. حدّث الصفحة لاحقاً أو تواصل معنا للمزيد."
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "type": "text", "content": reply})
                    else:
                        assistant_msg = run_image_pipeline(topic, status)
                        st.session_state.generations_made += 1
                        render_assistant_message(assistant_msg, key_suffix="new")
                        st.session_state.messages.append(assistant_msg)

                else:
                    status.update(label="بيرد عليك...")
                    reply = chat_reply(st.session_state.messages, user_text, HF_TOKEN)
                    status.update(label="تم", state="complete")
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "type": "text", "content": reply})

            except json.JSONDecodeError:
                status.update(label="حدث خطأ", state="error")
                err = "حدث خطأ في قراءة رد الذكاء الاصطناعي. حاول مرة أخرى أو أعد صياغة كلامك."
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": err})
            except Exception as e:
                status.update(label="حدث خطأ", state="error")
                print("[DEBUG] خطأ عام أثناء التوليد:")
                traceback.print_exc()
                err = f"حدث خطأ غير متوقع: {e}"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": err})

    st.session_state.pending = False
    st.rerun()


# ----------------------------------------------------------------------------
# الواجهة الرئيسية
# ----------------------------------------------------------------------------
if not st.session_state.messages:
    # ---------------- وضع الهبوط: بوكس واحد بس في نص الصفحة، بدون أي كلام ----------------
    st.markdown('<div class="landing-shell">', unsafe_allow_html=True)
    with st.form("landing_form", clear_on_submit=True):
        col_input, col_btn = st.columns([9, 1])
        with col_input:
            landing_text = st.text_area(
                "idea",
                placeholder="اسألني أي حاجة، أو اطلب صورة أو فيديو...",
                label_visibility="collapsed",
                height=68,
            )
        with col_btn:
            landing_submit = st.form_submit_button("➤")
    st.markdown('</div>', unsafe_allow_html=True)

    if landing_submit and landing_text.strip():
        queue_user_message(landing_text.strip())
        st.rerun()

else:
    # ---------------- وضع المحادثة: البوكس يفضل ثابت تحت، والردود تبان فوقه ----------------
    # نفس المسار ده بيتشغّل من أول رسالة، فالشكل مضبوط طول الوقت من غير وميض
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            render_assistant_message(msg, key_suffix=i)

    if st.session_state.pending:
        generate_reply()

    user_input = st.chat_input("اسألني أي حاجة، أو اطلب صورة أو فيديو...")
    if user_input:
        queue_user_message(user_input)
        st.rerun()
