import os
import tempfile
from datetime import timedelta
import streamlit as st
from yt_dlp import YoutubeDL

# ----------------- Helper Functions -----------------

def format_duration(seconds):
    if not seconds:
        return "Unknown"
    return str(timedelta(seconds=int(seconds)))

def bytes_to_human(n):
    if not n:
        return "?"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    return f"{n:.2f} {units[i]}"

def progress_hook(progress_bar, status_text):
    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                pct = downloaded / total
                progress_bar.progress(min(1.0, pct))
                status_text.write(
                    f"Downloading... {bytes_to_human(downloaded)} / {bytes_to_human(total)}"
                )
            else:
                status_text.write(f"Downloading... {bytes_to_human(downloaded)}")
        elif d["status"] == "finished":
            progress_bar.progress(1.0)
            status_text.write("Processing file...")
    return hook

def get_info(url):
    ydl_opts = {"quiet": True, "skip_download": True, "noplaylist": True}
    with YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def build_format_query(kind, quality, audio_codec="mp3"):
    height_map = {
        "Best": None,
        "1080p": 1080,
        "720p": 720,
        "480p": 480,
        "420p": 420,
        "360p": 360,
        "240p": 240,
        "144p": 144,
    }

    if kind == "Audio":
        fmt = "bestaudio/best"
        post = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_codec,
            "preferredquality": "192",
        }]
        return fmt, post, None

    h = height_map[quality]
    if h is None:
        fmt = "bv*+ba/b"
    else:
        fmt = f"bv*[height<={h}]+ba/b[height<={h}]"

    return fmt, [], "mp4"

def sanitize_filename(name):
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip() or "video"

# ----------------- Streamlit UI -----------------

st.set_page_config(page_title="YouTube Downloader", page_icon="▶️", layout="centered")
st.title("📥 YouTube Downloader")
st.caption("Download YouTube videos or audio in your chosen quality.")

with st.sidebar:
    st.header("Options")
    kind = st.radio("Download type", ["Video", "Audio"], index=0)
    quality = st.selectbox(
        "Quality",
        ["Best", "1080p", "720p", "480p", "420p", "360p", "240p", "144p"],
        index=0
    )
    audio_codec = st.selectbox("Audio format", ["mp3", "m4a"], index=0, disabled=(kind != "Audio"))

url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
fetch = st.button("Fetch Info")

if "info" not in st.session_state:
    st.session_state.info = None

if fetch and url.strip():
    try:
        with st.spinner("Fetching video info..."):
            st.session_state.info = get_info(url.strip())
    except Exception as e:
        st.error(f"Failed to fetch info: {e}")
        st.session_state.info = None

info = st.session_state.info

if info:
    col1, col2 = st.columns([1, 2])
    with col1:
        thumb = None
        if info.get("thumbnails"):
            thumb = sorted(info["thumbnails"], key=lambda t: t.get("width", 0))[-1].get("url")
        if thumb:
            st.image(thumb, use_column_width=True)
    with col2:
        st.subheader(info.get("title", "Untitled"))
        st.write(f"Channel: {info.get('uploader', 'Unknown')}")
        st.write(f"Duration: {format_duration(info.get('duration'))}")
        if info.get("view_count"):
            st.write(f"Views: {info['view_count']:,}")

    if st.button("Download", type="primary"):
        progress = st.progress(0.0)
        status_text = st.empty()

        fmt_selector, postprocessors, merge_to = build_format_query(kind, quality, audio_codec)
        out_name = sanitize_filename(info.get("title", "video"))

        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = os.path.join(tmpdir, f"{out_name}.%(ext)s")
            ydl_opts = {
                "format": fmt_selector,
                "noplaylist": True,
                "outtmpl": outtmpl,
                "progress_hooks": [progress_hook(progress, status_text)],
                "postprocessors": postprocessors,
                "quiet": True,
            }
            if merge_to:
                ydl_opts["merge_output_format"] = merge_to

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir)]
                if files:
                    out_file = files[0]
                    ext = os.path.splitext(out_file)[1].lower().lstrip(".")
                    mime = "audio/mpeg" if ext == "mp3" else "video/mp4"
                    with open(out_file, "rb") as f:
                        st.download_button(
                            label=f"Save {os.path.basename(out_file)}",
                            data=f.read(),
                            file_name=os.path.basename(out_file),
                            mime=mime
                        )
                    status_text.success("Download ready!")
                else:
                    st.error("No file found after download.")
            except Exception as e:
                st.error(f"Download failed: {e}")
