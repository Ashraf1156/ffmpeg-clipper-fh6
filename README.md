# 🎬 StreamCut R2 - In-Memory Video Clipper & Zernio Social Media Publisher

A high-performance Python & Streamlit desktop application for trimming video clips, stitching optional **Subscribe & Follow outro templates**, streaming MP4 bytes in-memory directly to **Cloudflare R2 Storage**, and scheduling/publishing Instagram Reels and social media posts instantly via **Zernio REST API**.

---

## ✨ Features & Architecture

- **Zero Temporary Disk Overhead**:
  - Uses FFmpeg in-memory pipe processing (`pipe:1`) to trim source video clips and stitch outro templates on-the-fly.
  - Streams `io.BytesIO` stdout directly to Cloudflare R2 using `boto3.upload_fileobj`.

- **Outro Animation Concatenator**:
  - Optionally concatenates a 5-second **Subscribe & Follow** animation template to the end of every generated clip using FFmpeg `concat` complex filter graph.

- **Direct Cloudflare R2 Cloud Storage**:
  - Direct integration with Cloudflare R2 S3-compatible API.
  - Supports custom R2 public domains (`r2.dev` / custom domains) for instant public HTTPS video link generation required by Instagram & social platforms.

- **Zernio REST API Publisher & Scheduler**:
  - **Publish Immediately (Now)**: Publishes Instagram Reels directly without queuing.
  - **Schedule for Later**: Schedules posts for future date and time.
  - Formats payload parameters (`content`, `status`, `mediaItems`, `postType`) to comply 100% with Zernio's API schema.

- **Status & Clip Management Dashboard**:
  - Tracks all clip metadata locally in SQLite (`metadata.db`).
  - Interactive pop-up dialogs to preview source, template, and uploaded R2 video clips.
  - Batch deletion tool to select and delete video objects directly from Cloudflare R2 storage and database simultaneously.

---

## 🛠️ Prerequisites & Installation

### 1. System Requirements & FFmpeg

Ensure **FFmpeg** is installed and accessible on your system `PATH`:

- **Windows**:
  ```cmd
  winget install Gyan.FFmpeg
  ```
- **macOS**:
  ```bash
  brew install ffmpeg
  ```
- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```

---

### 2. Installation & Python Setup

```bash
# Clone the repository
git clone https://github.com/Ashraf1156/ffmpeg-clipper-fh6.git
cd ffmpeg-clipper-fh6

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

---

## 🔑 Configuration (`.streamlit/secrets.toml`)

Create a `.streamlit/secrets.toml` file (or copy from `.streamlit/secrets.toml.example`) and fill in your credentials:

```toml
[r2]
account_id = "YOUR_CLOUDFLARE_ACCOUNT_ID"
access_key_id = "YOUR_R2_ACCESS_KEY_ID"
secret_access_key = "YOUR_R2_SECRET_ACCESS_KEY"
bucket_name = "YOUR_R2_BUCKET_NAME"
public_domain = "https://pub-xxxx.r2.dev" # Public R2 domain for Instagram scraping

[zernio]
api_key = "YOUR_ZERNIO_API_KEY"

[platforms]
instagram_account_id = "YOUR_24_CHAR_INSTAGRAM_ACCOUNT_ID"
youtube_account_id = "YOUR_YOUTUBE_ACCOUNT_ID"
```

> **Note**:
> To retrieve your 24-character Instagram Account ID in Zernio:
> Go to **Zernio Dashboard ➔ Connections**, locate your Instagram account card, and click the copy icon (`📋`) next to your username.

---

## 🚀 Running the Application

Launch the Streamlit app:

```bash
streamlit run app.py
```

The application will open in your default browser at `http://localhost:8501`.

---

## 📦 Building Standalone Windows Executable (`.exe`)

You can compile **StreamCut R2** into a standalone Windows `.exe` application that runs without needing Python pre-installed:

### Option A: Automatic Batch Script (Recommended)
Double-click **`build_exe.bat`** (or run `.\build_exe.bat` in Terminal).

### Option B: Manual Command
```cmd
# 1. Install PyInstaller
pip install pyinstaller

# 2. Build .exe bundle
pyinstaller --noconfirm --onedir --name "StreamCut_R2" ^
  --copy-metadata streamlit ^
  --collect-all streamlit ^
  --add-data "app.py;." ^
  --add-data ".streamlit;.streamlit" ^
  run_app.py
```

The compiled standalone executable will be output in:
`dist\StreamCut_R2\StreamCut_R2.exe`

Double-clicking `StreamCut_R2.exe` launches the background engine and opens the application in your browser automatically!

---

## 📁 Project Structure

```text
ffmpeg-clipper-fh6/
├── app.py                         # Main Streamlit application logic
├── requirements.txt               # Python package dependencies
├── .streamlit/
│   ├── secrets.toml.example       # Credentials template
│   └── secrets.toml               # Private credentials (git-ignored)
├── metadata.db                    # Local SQLite metadata cache (git-ignored)
├── .gitignore                     # Git exclusion definitions
└── README.md                      # Project documentation
```

---

## 📜 License

Distributed under the MIT License.
