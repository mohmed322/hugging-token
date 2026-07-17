import streamlit as st
import yt_dlp
import os
import re
import shutil

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

# فحص وجود ffmpeg في السيرفر وعرض حالته للمستخدم للمساعدة في التشخيص
ffmpeg_path = shutil.which("ffmpeg")
if ffmpeg_path:
    st.sidebar.success("✅ أداة القص (FFmpeg) جاهزة ومتصلة بالسيرفر!")
else:
    st.sidebar.error("⚠️ تحذير: أداة FFmpeg لم يتم تفعيلها بالسيرفر بعد. تأكد من وجود ملف packages.txt وإعادة بناء التطبيق.")

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
    else:
        start_secs = time_to_seconds(start_time)
        end_secs = time_to_seconds(end_time)
        
        if start_secs is None or end_secs is None:
            st.error("❌ صيغة الوقت غير صحيحة. يرجى استخدام الصيغة (ساعة:دقيقة:ثانية) مثل: 00:01:15")
        elif start_secs >= end_secs:
            st.error("❌ يجب أن يكون وقت البداية أقل من وقت النهاية!")
        else:
            output_filename = "clipped_video.mp4"
            
            if os.path.exists(output_filename):
                os.remove(output_filename)
                
            st.info("🔄 جاري الاتصال بيوتيوب وقص المقطع... قد يستغرق ذلك ثوانٍ.")
            
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': output_filename,
                'download_ranges': lambda info_dict, ydl: [{
                    'start_time': start_secs,
                    'end_time': end_secs,
                }],
                'force_keyframes_at_cuts': True,
                'quiet': True,
                'no_warnings': True
            }
            
            # إذا عثرنا على ffmpeg نمرر مساره للأداة للتأكيد
            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = ffmpeg_path
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                    
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
                    st.error("❌ فشل معالجة الفيديو.")
                    
            except Exception as e:
                st.error(f"🚨 حدث خطأ أثناء المعالجة: {str(e)}")
