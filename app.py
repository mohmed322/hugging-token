import streamlit as st
import yt_dlp
import os
import re
import shutil
import subprocess

# إعدادات الصفحة العامة
st.set_page_config(
    page_title="قاصّ اليوتيوب الذكي",
    page_icon="✂️",
    layout="centered"
)

# كود CSS لتحسين المظهر ودعم اللغة العربية
st.markdown("""
    <style>
    .reportview-container {
        direction: rtl;
        text-align: right;
    }
    div.stButton > button:first-child {
        background-color: #ff4b4b;
        color: white;
        border-radius: 8px;
        width: 100%;
        font-size: 18px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.title("✂️ أداة قص وتحميل مقاطع اليوتيوب مجاناً")
st.write("ضع رابط الفيديو وحدد الوقت المطلوب لقص المقطع وتحميله مباشرة وبأعلى جودة.")

st.divider()

# فحص وجود ffmpeg في السيرفر
ffmpeg_path = shutil.which("ffmpeg")
if ffmpeg_path:
    st.sidebar.success("✅ أداة القص (FFmpeg) جاهزة ومتصلة بالسيرفر!")
else:
    st.sidebar.error("⚠️ تحذير: أداة FFmpeg لم يتم تفعيلها بالسيرفر بعد. تأكد من وجود ملف packages.txt")

video_url = st.text_input("🔗 ضع رابط فيديو اليوتيوب هنا:", placeholder="https://www.youtube.com/watch?v=...")

st.write("⏱️ **حدد فترة المقطع المراد قصه (ساعة:دقيقة:ثانية):**")
col1, col2 = st.columns(2)

with col1:
    start_time = st.text_input("نقطة البداية:", value="00:00:10")
with col2:
    end_time = st.text_input("نقطة النهاية:", value="00:00:40")

st.divider()

def time_to_seconds(t_str):
    try:
        parts = list(map(int, t_str.split(':')))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        else:
            return int(parts[0])
    except ValueError:
        return None

def is_valid_youtube_url(url):
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    return re.match(youtube_regex, url) is not None

if st.button("🚀 معالجة وقص المقطع الآن"):
    if not video_url:
        st.warning("⚠️ يرجى إدخال رابط الفيديو أولاً!")
    elif not is_valid_youtube_url(video_url):
        st.error("❌ رابط اليوتيوب غير صحيح.")
    elif not ffmpeg_path:
        st.error("❌ لا يمكن القص لأن FFmpeg غير متوفر على السيرفر.")
    else:
        start_secs = time_to_seconds(start_time)
        end_secs = time_to_seconds(end_time)
        
        if start_secs is None or end_secs is None:
            st.error("❌ صيغة الوقت غير صحيحة. يرجى استخدام الصيغة (ساعة:دقيقة:ثانية) مثل: 00:01:15")
        elif start_secs >= end_secs:
            st.error("❌ يجب أن يكون وقت البداية أقل من وقت النهاية!")
        else:
            temp_full_video = "temp_full_video.mp4"
            output_filename = "clipped_video.mp4"
            
            for temp_file in [temp_full_video, output_filename]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
            st.info("🔄 جاري تحميل الفيديو كاملاً على السيرفر السحابي بأقصى سرعة...")
            
            # إعدادات متقدمة جداً لتجاوز جدار حظر يوتيوب 403 الجديد
            ydl_opts = {
                'format': 'best[ext=mp4]/best', 
                'outtmpl': temp_full_video,
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                # إجبار الأداة على استخدام بروتوكول تطبيق الموبايل الرسمي لتجنب الحجب
                'extractor_args': {
                    'youtube': {
                        'player_client': ['ios', 'android'],
                        'player_skip': ['webpage', 'configs'],
                    }
                },
                # ترويسات متصفح عشوائية ومتكاملة ومحدثة
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Sec-Fetch-Mode': 'navigate',
                }
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                
                if os.path.exists(temp_full_video):
                    st.info("✂️ جاري الآن قص الجزء المطلوب بدقة عالية...")
                    
                    duration_secs = end_secs - start_secs
                    
                    cmd = [
                        ffmpeg_path,
                        "-ss", str(start_secs),
                        "-i", temp_full_video,
                        "-t", str(duration_secs),
                        "-c", "copy",
                        output_filename
                    ]
                    
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    if os.path.exists(temp_full_video):
                        os.remove(temp_full_video)
                        
                    if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
                        st.success("🎉 تم قص المقطع بنجاح واكتمال المعالجة!")
                        st.video(output_filename)
                        
                        with open(output_filename, "rb") as file:
                            st.download_button(
                                label="📥 اضغط هنا لتحميل المقطع إلى جهازك",
                                data=file,
                                file_name="youtube_clip.mp4",
                                mime="video/mp4"
                            )
                    else:
                        st.error("❌ فشل معالجة وقص الفيديو محلياً.")
                else:
                    st.error("❌ فشل تحميل الفيديو الأصلي بسبب قيود الحماية الصارمة من يوتيوب.")
                    
            except Exception as e:
                st.error(f"🚨 حدث خطأ أثناء المعالجة: {str(e)}")
