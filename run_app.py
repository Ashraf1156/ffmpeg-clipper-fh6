import os
import sys
import webbrowser
import threading
import time
import streamlit.web.cli as stcli

def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    app_path = os.path.join(base_dir, "app.py")
    
    # Open browser automatically after 2 seconds
    threading.Thread(target=open_browser, daemon=True).start()
    
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.port=8501",
        "--server.headless=true"
    ]
    sys.exit(stcli.main())
