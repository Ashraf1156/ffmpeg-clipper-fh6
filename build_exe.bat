@echo off
echo Building StreamCut R2 Standalone Windows Executable (.exe)...
pip install pyinstaller streamlit boto3 requests imageio_ffmpeg toml
pyinstaller --noconfirm --onedir --name "StreamCut_R2" ^
  --copy-metadata streamlit ^
  --collect-all streamlit ^
  --add-data "app.py;." ^
  --add-data ".streamlit;.streamlit" ^
  run_app.py
echo.
echo Build complete! Executable is located in dist\StreamCut_R2\StreamCut_R2.exe
pause
