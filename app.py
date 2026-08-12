import io
import os
import json
import uuid
import sqlite3
import subprocess
import datetime
import requests
import boto3
import streamlit as st
import tkinter as tk
from tkinter import filedialog
import shutil
import imageio_ffmpeg
import toml

# ==========================================
# PAGE CONFIGURATION & THEME-ADAPTIVE STYLING
# ==========================================
st.set_page_config(
    page_title="StreamCut R2 - Video Clipper & Scheduler",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* Theme-Adaptive Status Badges */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        border-radius: 4px;
        line-height: 1;
    }
    .badge-saved {
        background-color: rgba(108, 117, 125, 0.15);
        color: var(--text-color);
        border: 1px solid rgba(108, 117, 125, 0.3);
    }
    .badge-scheduled {
        background-color: rgba(217, 119, 6, 0.15);
        color: #d97706;
        border: 1px solid rgba(217, 119, 6, 0.4);
    }
    .badge-posted {
        background-color: rgba(21, 128, 61, 0.15);
        color: #15803d;
        border: 1px solid rgba(21, 128, 61, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# POPUP DIALOG FOR VIDEO PREVIEW
# ==========================================
@st.dialog("Video Preview", width="large")
def preview_video_dialog(video_url_or_path, title_label=""):
    st.markdown(f"**{title_label}**")
    if video_url_or_path:
        st.video(video_url_or_path)
    else:
        st.info("No video file or URL available for preview.")

# ==========================================
# DATABASE HELPER (metadata.db)
# ==========================================
DB_FILE = "metadata.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_id TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            r2_key TEXT NOT NULL,
            r2_url TEXT,
            source_path TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'SAVED_IN_R2',
            scheduled_at TEXT,
            platforms TEXT,
            caption TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def load_app_secrets():
    sec_path = os.path.join(".streamlit", "secrets.toml")
    if os.path.exists(sec_path):
        try:
            return toml.load(sec_path)
        except Exception:
            pass
    return st.secrets

# ==========================================
# CLOUDFLARE R2 CLIENT HELPER
# ==========================================
def get_r2_client():
    secrets = load_app_secrets()
    r2_secrets = secrets.get("r2", {})
    account_id = r2_secrets.get("account_id", "")
    access_key = r2_secrets.get("access_key_id", "")
    secret_key = r2_secrets.get("secret_access_key", "")
    endpoint_url = r2_secrets.get("endpoint_url") or f"https://{account_id}.r2.cloudflarestorage.com"
    
    if not (account_id and access_key and secret_key):
        st.error("Cloudflare R2 credentials missing in .streamlit/secrets.toml")
        st.stop()
        
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto"
    )

# ==========================================
# TKINTER NATIVE FILE PICKER & FFMPEG RESOLVER
# ==========================================
def get_ffmpeg_executable():
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def select_local_file(title="Select Video File"):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = filedialog.askopenfilename(
        title=title,
        filetypes=[
            ("Video Files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.flv"),
            ("All Files", "*.*")
        ]
    )
    root.destroy()
    return file_path

# ==========================================
# MODULE A: IN-MEMORY CLIPPER & R2 UPLOADER
# ==========================================
def cut_and_upload_to_r2(source_path, start_time, end_time, label, template_path=None):
    ffmpeg_exe = get_ffmpeg_executable()
    
    if template_path and os.path.exists(template_path):
        cmd = [
            ffmpeg_exe,
            "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", str(source_path),
            "-i", str(template_path),
            "-filter_complex", "[0:v][0:a][1:v][1:a] concat=n=2:v=1:a=1 [v] [a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4",
            "pipe:1"
        ]
    else:
        cmd = [
            ffmpeg_exe,
            "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", str(source_path),
            "-c", "copy",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4",
            "pipe:1"
        ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout_bytes, stderr_bytes = process.communicate()
    
    if process.returncode != 0:
        error_msg = stderr_bytes.decode("utf-8", errors="ignore")
        raise RuntimeError(f"FFmpeg process error: {error_msg}")
        
    buffer = io.BytesIO(stdout_bytes)
    
    clip_uuid = str(uuid.uuid4())[:8]
    sanitized_label = "".join(c for c in label if c.isalnum() or c in ("-", "_")).strip() or "clip"
    r2_key = f"clips/{clip_uuid}_{sanitized_label}.mp4"
    
    s3_client = get_r2_client()
    app_sec = load_app_secrets()
    bucket_name = app_sec.get("r2", {}).get("bucket_name", "")
    
    s3_client.upload_fileobj(
        buffer,
        bucket_name,
        r2_key,
        ExtraArgs={"ContentType": "video/mp4"}
    )
    
    public_domain = app_sec.get("r2", {}).get("public_domain", "")
    if public_domain:
        r2_url = f"{public_domain.rstrip('/')}/{r2_key}"
    else:
        r2_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": r2_key},
            ExpiresIn=604800
        )
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO clips (clip_id, label, r2_key, r2_url, source_path, start_time, end_time, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'SAVED_IN_R2')
    """, (clip_uuid, label, r2_key, r2_url, source_path, start_time, end_time))
    conn.commit()
    conn.close()
    
    return clip_uuid, r2_key, r2_url

# ==========================================
# MODULE B: ZERNIO SCHEDULER & PUBLISHER HANDLER
# ==========================================
def schedule_clip_via_zernio(clip_row, platform_targets, caption, schedule_datetime, publish_now=False, post_type="reel"):
    app_sec = load_app_secrets()
    zernio_secrets = app_sec.get("zernio", {})
    api_key = zernio_secrets.get("api_key", "")
    if not api_key:
        raise ValueError("Zernio API Key missing in secrets.toml under [zernio]")
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    iso_timestamp = schedule_datetime.strftime("%Y-%m-%dT%H:%M:%SZ") if (schedule_datetime and not publish_now) else None
    
    s3_client = get_r2_client()
    r2_sec = app_sec.get("r2", {})
    bucket_name = r2_sec.get("bucket_name", "")
    public_domain = r2_sec.get("public_domain", "")
    
    if public_domain:
        media_url = f"{public_domain.rstrip('/')}/{clip_row['r2_key']}"
    else:
        media_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": clip_row["r2_key"]},
            ExpiresIn=604800
        )
        
    formatted_platforms = []
    for item in platform_targets:
        if isinstance(item, dict):
            acc_id = item.get("accountId") or item.get("account") or item.get("id")
            plat_name = item.get("platform", "instagram")
            formatted_platforms.append({
                "platform": plat_name,
                "account": acc_id,
                "accountId": acc_id,
                "type": post_type,
                "postType": post_type,
                "placement": post_type
            })
        elif isinstance(item, str):
            p_name = "instagram" if "instagram" in item.lower() else ("youtube" if "youtube" in item.lower() else "social")
            formatted_platforms.append({
                "platform": p_name,
                "account": item,
                "accountId": item,
                "type": post_type,
                "postType": post_type,
                "placement": post_type
            })
            
    payload = {
        "platforms": formatted_platforms,
        "content": caption,
        "caption": caption,
        "status": "published" if publish_now else "scheduled",
        "publishNow": publish_now,
        "isDraft": False,
        "postType": post_type,
        "instagramType": post_type,
        "mediaItems": [
            {
                "url": media_url,
                "type": "video"
            }
        ],
        "media": [
            {
                "url": media_url,
                "type": "video"
            }
        ],
        "mediaUrls": [media_url]
    }
    
    if not publish_now and iso_timestamp:
        payload["scheduledAt"] = iso_timestamp
        
    response = requests.post(
        "https://zernio.com/api/v1/posts",
        headers=headers,
        json=payload,
        timeout=30
    )
    
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Zernio API Error ({response.status_code}): {response.text}")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    new_status = "POSTED" if publish_now else "SCHEDULED"
    cursor.execute("""
        UPDATE clips
        SET status = ?, scheduled_at = ?, platforms = ?, caption = ?, r2_url = ?
        WHERE id = ?
    """, (new_status, iso_timestamp, json.dumps(formatted_platforms), caption, media_url, clip_row["id"]))
    conn.commit()
    conn.close()
    
    return response.json()

# ==========================================
# MODULE C: BATCH CLEANUP HELPER
# ==========================================
def delete_clips_from_r2_and_db(clip_db_ids):
    if not clip_db_ids:
        return 0
        
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(clip_db_ids))
    cursor.execute(f"SELECT id, r2_key FROM clips WHERE id IN ({placeholders})", clip_db_ids)
    rows = cursor.fetchall()
    
    if not rows:
        conn.close()
        return 0
        
    objects_to_delete = [{"Key": row["r2_key"]} for row in rows]
    
    s3_client = get_r2_client()
    app_sec = load_app_secrets()
    bucket_name = app_sec.get("r2", {}).get("bucket_name", "")
    
    s3_client.delete_objects(
        Bucket=bucket_name,
        Delete={"Objects": objects_to_delete}
    )
    
    cursor.execute(f"DELETE FROM clips WHERE id IN ({placeholders})", clip_db_ids)
    conn.commit()
    conn.close()
    
    return len(rows)

# ==========================================
# MAIN APPLICATION INTERFACE
# ==========================================
st.title("StreamCut R2")
st.caption("In-Memory Video Trimmer, Outro Concatenator, Cloudflare R2 Streamer & Social Media Scheduler")
st.markdown("<br>", unsafe_allow_html=True)

if "source_video_path" not in st.session_state:
    st.session_state.source_video_path = ""
if "template_video_path" not in st.session_state:
    st.session_state.template_video_path = ""
if "clip_ranges" not in st.session_state:
    st.session_state.clip_ranges = [{"from": "00:00:00", "to": "00:00:25", "label": "Clip 1"}]

tab_clip, tab_schedule, tab_dashboard = st.tabs([
    "Module A: In-Memory Clipper & R2 Upload",
    "Module B: Social Media Scheduler & Instant Publisher",
    "Module C: Status Management & Cleanup"
])

# ------------------------------------------
# TAB A: IN-MEMORY CLIPPER & R2 UPLOADER
# ------------------------------------------
with tab_clip:
    st.subheader("1. Source Video Selection (Hook + Main Content)")
    c_src_browse, c_src_prev, c_src_path = st.columns([1.5, 1.5, 3], vertical_alignment="center")
    with c_src_browse:
        if st.button("Browse Source Video", use_container_width=True):
            selected_path = select_local_file("Select Source Video File")
            if selected_path:
                st.session_state.source_video_path = selected_path
                st.rerun()
    with c_src_prev:
        if st.session_state.source_video_path:
            if st.button("Preview Source Video", use_container_width=True):
                preview_video_dialog(st.session_state.source_video_path, "Source Video Preview")
    with c_src_path:
        if st.session_state.source_video_path:
            st.success(f"**Selected Source File:** `{st.session_state.source_video_path}`")
        else:
            st.caption("No source file selected.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("2. Outro / Subscribe Animation Template Video (Optional)")
    st.caption("Select a 5-second Subscribe & Follow animation template video to append at the end of every clip:")
    c_tmpl_browse, c_tmpl_prev, c_tmpl_path = st.columns([1.5, 1.5, 3], vertical_alignment="center")
    with c_tmpl_browse:
        if st.button("Browse Template Video", use_container_width=True):
            selected_tmpl_path = select_local_file("Select Subscribe & Follow Template Video")
            if selected_tmpl_path:
                st.session_state.template_video_path = selected_tmpl_path
                st.rerun()
    with c_tmpl_prev:
        if st.session_state.template_video_path:
            if st.button("Preview Template Video", use_container_width=True):
                preview_video_dialog(st.session_state.template_video_path, "Outro Template Video Preview")
    with c_tmpl_path:
        if st.session_state.template_video_path:
            st.info(f"**Selected Outro Template:** `{st.session_state.template_video_path}`")
        else:
            st.caption("No template video selected (clips will be uploaded without outro).")
            
    if st.session_state.template_video_path:
        use_template = st.checkbox("Append Subscribe & Follow Outro Template to generated clips", value=True)
    else:
        use_template = False

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("3. Dynamic Clip Range Builder (Hook + Content)")
    st.caption("Define start time (hh:mm:ss), end time (hh:mm:ss), and label for each clip:")
    
    to_remove = []
    for idx, clip in enumerate(st.session_state.clip_ranges):
        c1, c2, c3, c4 = st.columns([2, 2, 3, 1], vertical_alignment="bottom")
        with c1:
            clip["from"] = st.text_input(f"From (start)", value=clip["from"], key=f"from_{idx}")
        with c2:
            clip["to"] = st.text_input(f"To (end)", value=clip["to"], key=f"to_{idx}")
        with c3:
            clip["label"] = st.text_input(f"Clip Label", value=clip["label"], key=f"label_{idx}")
        with c4:
            if st.button("Remove", key=f"del_{idx}", use_container_width=True):
                to_remove.append(idx)
                
    if to_remove:
        for idx in sorted(to_remove, reverse=True):
            st.session_state.clip_ranges.pop(idx)
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    col_add, col_space = st.columns([1, 3])
    with col_add:
        if st.button("+ Add Another Clip Range", use_container_width=True):
            st.session_state.clip_ranges.append({
                "from": "00:00:00",
                "to": "00:00:25",
                "label": f"Clip {len(st.session_state.clip_ranges)+1}"
            })
            st.rerun()

    st.divider()
    if st.button("Cut & Upload directly to R2", type="primary", use_container_width=True):
        if not st.session_state.source_video_path:
            st.error("Please select a local source video file first.")
        elif not os.path.exists(st.session_state.source_video_path):
            st.error(f"Source video file path does not exist: {st.session_state.source_video_path}")
        elif not st.session_state.clip_ranges:
            st.error("Please add at least one clip range.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_clips = len(st.session_state.clip_ranges)
            
            active_template = st.session_state.template_video_path if (use_template and st.session_state.template_video_path) else None
            
            success_count = 0
            for i, clip in enumerate(st.session_state.clip_ranges):
                msg = f"Processing Clip {i+1}/{total_clips}: '{clip['label']}'"
                if active_template:
                    msg += " (Stitching with Outro Template Video)..."
                else:
                    msg += "..."
                status_text.text(msg)
                
                try:
                    uuid_id, r2_key, r2_url = cut_and_upload_to_r2(
                        source_path=st.session_state.source_video_path,
                        start_time=clip["from"],
                        end_time=clip["to"],
                        label=clip["label"],
                        template_path=active_template
                    )
                    st.success(f"Successfully clipped & stitched '{clip['label']}' directly to R2 (Key: {r2_key})")
                    success_count += 1
                except Exception as e:
                    st.error(f"Failed to clip '{clip['label']}': {e}")
                progress_bar.progress((i + 1) / total_clips)
                
            status_text.text(f"Processing complete: {success_count}/{total_clips} clips uploaded to Cloudflare R2.")

# ------------------------------------------
# TAB B: SOCIAL SCHEDULER & INSTANT PUBLISHER
# ------------------------------------------
with tab_schedule:
    st.subheader("Schedule or Instantly Publish Clips via Zernio REST API")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clips ORDER BY created_at DESC")
    all_clips = cursor.fetchall()
    conn.close()
    
    if not all_clips:
        st.info("No clips saved in database yet. Process and upload clips in Module A first.")
    else:
        clip_options = {f"#{c['id']} - {c['label']} [{c['status']}]": c for c in all_clips}
        
        c_sel_box, c_sel_prev = st.columns([3, 1], vertical_alignment="bottom")
        with c_sel_box:
            selected_clip_label = st.selectbox("Select Target Clip", list(clip_options.keys()))
            selected_clip = clip_options[selected_clip_label]
        with c_sel_prev:
            if selected_clip and selected_clip["r2_url"]:
                if st.button("Preview Clip Video", use_container_width=True):
                    preview_video_dialog(selected_clip["r2_url"], f"Clip Preview: {selected_clip['label']}")
        
        st.markdown(f"**Clip Details:** Label: `{selected_clip['label']}` | R2 Key: `{selected_clip['r2_key']}` | Status: `{selected_clip['status']}`")
        
        st.markdown("#### Select Target Platforms")
        app_sec = load_app_secrets()
        plat_secrets = app_sec.get("platforms", {})
        ig_account_id = plat_secrets.get("instagram_account_id", "INSTAGRAM_ACCOUNT_ID")
        yt_account_id = plat_secrets.get("youtube_account_id", "YOUTUBE_ACCOUNT_ID")
        
        col_ig, col_yt = st.columns(2)
        with col_ig:
            use_ig = st.checkbox(f"Instagram (ID: {ig_account_id})", value=True)
        with col_yt:
            use_yt = st.checkbox(f"YouTube (ID: {yt_account_id})", value=True)
            
        caption = st.text_area("Post Caption", value=selected_clip['caption'] or f"Check out this clip: {selected_clip['label']} #video #trending")
        
        col_mode, col_format = st.columns(2)
        with col_mode:
            publish_action = st.radio("Publishing Action", ["Publish Immediately (Now)", "Schedule for Future Date & Time"], horizontal=False)
        with col_format:
            ig_format = st.radio("Instagram Video Type", ["Reel (Recommended for clips)", "Feed Post"], horizontal=False)
            
        publish_now_flag = (publish_action == "Publish Immediately (Now)")
        post_type_val = "reel" if "Reel" in ig_format else "post"
        
        if not publish_now_flag:
            col_d, col_t = st.columns(2)
            with col_d:
                sched_date = st.date_input("Schedule Date", value=datetime.date.today() + datetime.timedelta(days=1))
            with col_t:
                sched_time = st.time_input("Schedule Time", value=datetime.time(15, 0))
            sched_dt = datetime.datetime.combine(sched_date, sched_time)
        else:
            sched_dt = datetime.datetime.now()
            
        btn_text = "🚀 Publish Reel Immediately via Zernio" if publish_now_flag else "📅 Schedule Clip via Zernio"
        
        if st.button(btn_text, type="primary", use_container_width=True):
            clean_ig_id = ig_account_id.strip()
            clean_yt_id = yt_account_id.strip()
            
            if use_ig and ("YOUR_INSTAGRAM" in clean_ig_id or not clean_ig_id):
                st.error("Please update instagram_account_id in .streamlit/secrets.toml with your real Zernio Account ID.")
            elif use_ig and len(clean_ig_id) != 24:
                st.error(f"Instagram Account ID must be exactly 24 characters (current length: {len(clean_ig_id)}). Please copy the exact 24-character Account ID from Zernio Connections page.")
            elif use_yt and ("YOUR_YOUTUBE" in clean_yt_id or not clean_yt_id):
                st.error("Please update youtube_account_id in .streamlit/secrets.toml with your real Zernio Account ID.")
            else:
                selected_platform_targets = []
                if use_ig:
                    selected_platform_targets.append({
                        "platform": "instagram",
                        "accountId": clean_ig_id
                    })
                if use_yt:
                    selected_platform_targets.append({
                        "platform": "youtube",
                        "accountId": clean_yt_id
                    })
                    
                if not selected_platform_targets:
                    st.error("Please select at least one target platform.")
                else:
                    try:
                        action_msg = "Publishing Reel immediately to Instagram via Zernio..." if publish_now_flag else "Scheduling post via Zernio..."
                        with st.spinner(action_msg):
                            resp = schedule_clip_via_zernio(
                                clip_row=selected_clip,
                                platform_targets=selected_platform_targets,
                                caption=caption,
                                schedule_datetime=sched_dt,
                                publish_now=publish_now_flag,
                                post_type=post_type_val
                            )
                        if publish_now_flag:
                            st.success("🎉 Reel successfully published immediately via Zernio API!")
                        else:
                            st.success("📅 Clip successfully scheduled via Zernio API!")
                        st.json(resp)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Zernio Error: {e}")

# ------------------------------------------
# TAB C: CLIP MANAGEMENT & BATCH CLEANUP
# ------------------------------------------
with tab_dashboard:
    st.subheader("Clip Management & Batch Cleanup Dashboard")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clips ORDER BY created_at DESC")
    clips_list = cursor.fetchall()
    conn.close()
    
    filter_option = st.radio(
        "Filter Status",
        ["All", "SAVED_IN_R2", "SCHEDULED", "POSTED"],
        horizontal=True
    )
    
    filtered_clips = clips_list
    if filter_option != "All":
        filtered_clips = [c for c in clips_list if c["status"] == filter_option]
        
    st.caption(f"Displaying {len(filtered_clips)} clips:")
    
    if not filtered_clips:
        st.info("No clips matching the selected filter.")
    else:
        if "selected_for_delete" not in st.session_state:
            st.session_state.selected_for_delete = set()
            
        col_btn1, col_btn2 = st.columns([1, 2])
        with col_btn1:
            if st.button("Select All POSTED Clips", use_container_width=True):
                posted_ids = {c["id"] for c in clips_list if c["status"] == "POSTED"}
                st.session_state.selected_for_delete.update(posted_ids)
                st.rerun()
        with col_btn2:
            if st.button("Delete Selected Clips from Cloudflare R2", type="primary", use_container_width=True):
                if not st.session_state.selected_for_delete:
                    st.warning("No clips selected for deletion.")
                else:
                    ids_to_del = list(st.session_state.selected_for_delete)
                    try:
                        with st.spinner("Deleting selected objects from Cloudflare R2 bucket..."):
                            count = delete_clips_from_r2_and_db(ids_to_del)
                        st.success(f"Successfully deleted {count} clips from Cloudflare R2 and database.")
                        st.session_state.selected_for_delete.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Deletion failed: {e}")
                        
        st.divider()
        
        for c in filtered_clips:
            status_html = ""
            if c["status"] == "POSTED":
                status_html = '<span class="badge badge-posted">POSTED</span>'
            elif c["status"] == "SCHEDULED":
                status_html = '<span class="badge badge-scheduled">SCHEDULED</span>'
            else:
                status_html = '<span class="badge badge-saved">SAVED_IN_R2</span>'
                
            c_sel, c_info, c_action = st.columns([0.5, 3.5, 2], vertical_alignment="center")
            
            with c_sel:
                is_selected = c["id"] in st.session_state.selected_for_delete
                checked = st.checkbox("", value=is_selected, key=f"chk_{c['id']}")
                if checked and not is_selected:
                    st.session_state.selected_for_delete.add(c["id"])
                elif not checked and is_selected:
                    st.session_state.selected_for_delete.remove(c["id"])
                    
            with c_info:
                st.markdown(f"**#{c['id']} - {c['label']}** {status_html}", unsafe_allow_html=True)
                st.caption(f"Time Range: {c['start_time']} -> {c['end_time']} | R2 Key: `{c['r2_key']}` | Created: {c['created_at']}")
                
            with c_action:
                if c["r2_url"]:
                    if st.button("Preview Video", key=f"prev_dash_{c['id']}", use_container_width=True):
                        preview_video_dialog(c["r2_url"], f"Clip #{c['id']} - {c['label']}")
                if c["scheduled_at"]:
                    st.caption(f"Scheduled: {c['scheduled_at']}")
            st.divider()
