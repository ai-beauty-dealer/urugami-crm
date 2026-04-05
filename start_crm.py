#!/usr/bin/env python3
import subprocess
import webbrowser
import time
import sys
import os

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("🚀 CRM ツールを起動しています...")
    
    # Start the Flask server in the background
    try:
        process = subprocess.Popen([sys.executable, "app.py"])
        
        # Wait a moment for the server to start
        time.sleep(2)
        
        # Open the browser
        print("🌍 ブラウザでツールを開きます: http://localhost:5001")
        webbrowser.open("http://localhost:5001")
        
        print("\n[重要] ツール使用中は、このターミナルを閉じないでください。")
        print("終了するには Ctrl + C を押してください。\n")
        
        process.wait()
    except KeyboardInterrupt:
        print("\n👋 終了します。")
        process.terminate()
    except Exception as e:
        print(f"❌ 起動エラー: {e}")

if __name__ == "__main__":
    main()
