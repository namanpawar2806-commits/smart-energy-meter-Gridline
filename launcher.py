import os
import threading
import time
import webbrowser
from pathlib import Path
import uvicorn
BASE = Path(__file__).resolve().parent
os.chdir(BASE)

def open_browser():
 time.sleep(2)
 webbrowser.open("http://127.0.0.1:8001")

thread = threading.Thread(target=open_browser, daemon=True)
thread.start()
uvicorn.run(
    "app:app",
     host="127.0.0.1",
     port=8001,
     reload=False
       )
