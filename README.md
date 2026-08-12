# 🎬 StreamCut R2 - Direct Video Clipper & Social Media Scheduler

A pure Python Streamlit desktop application that trims video clips from a local source file with **zero local disk saving**, streams stdout directly into **Cloudflare R2** storage via `boto3`, schedules posts to **Instagram** and **YouTube** via **Zernio REST API**, and manages clip statuses via a local SQLite database (`metadata.db`).

---

## 🛠️ Features & Technical Highlights

1. **Zero Local File Disk Saving**:
   - Uses FFmpeg CLI with `-movflags frag_keyframe+empty_moov -f mp4 pipe:1` to stream directly to standard output stdout.
   - Captures stdout as an in-memory byte stream (`io.BytesIO`) and streams directly into Cloudflare R2 (`s3.upload_fileobj`).
2. **Native Local File Picker**:
   - Integrates Tkinter (`filedialog.askopenfilename`) for native OS file selection window.
3. **Zernio API Social Scheduler**:
   - Generates presigned R2 media URLs (7 days validity) or public domain URLs.
   - Multi-select Instagram (`INSTAGRAM_ACCOUNT_ID`) and YouTube (`YOUTUBE_ACCOUNT_ID`).
   - Posts to `https://zernio.com/api/v1/posts` with ISO timestamps & captions.
4. **Status Management & Batch Cleanup**:
   - Color-coded status badges: 🟢 `POSTED`, 🟠 `SCHEDULED`, ⚪ `SAVED_IN_R2`.
   - Batch selection and deletion from Cloudflare R2 bucket (`delete_objects`) & SQLite `metadata.db`.

---

## 🚀 Setup & Installation Instructions

### 1. Prerequisites & FFmpeg Installation

Ensure **FFmpeg** is installed and added to your system `PATH`.

- **Windows**:
  - Download binary from [Gybex / Bytedance / ffmpeg.org](https://ffmpeg.org/download.html) or install via `winget`:
    ```cmd
    winget install Gyan.FFmpeg
    ```
  - Verify in terminal: `ffmpeg -version`
- **macOS**:
  ```bash
  brew install ffmpeg
  ```
- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```

---

### 2. Python Environment Setup

Clone or open the repository, then create a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate on Windows:
venv\Scripts\activate

# Activate on macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

### 3. Configure Credentials (`.streamlit/secrets.toml`)

Update `.streamlit/secrets.toml` with your Cloudflare R2, Zernio, and Social Account credentials:

```toml
[r2]
account_id = "YOUR_CLOUDFLARE_ACCOUNT_ID"
access_key_id = "YOUR_R2_ACCESS_KEY_ID"
secret_access_key = "YOUR_R2_SECRET_ACCESS_KEY"
bucket_name = "YOUR_R2_BUCKET_NAME"
public_domain = "" # Optional public bucket domain e.g. "https://pub-xxxx.r2.dev"

[zernio]
api_key = "YOUR_ZERNIO_API_KEY"

[platforms]
instagram_account_id = "YOUR_INSTAGRAM_ACCOUNT_ID"
youtube_account_id = "YOUR_YOUTUBE_ACCOUNT_ID"
```

---

### 4. Running the Desktop Application

Launch Streamlit app:

```bash
streamlit run app.py
```

The application will open automatically in your web browser at `http://localhost:8501`.
