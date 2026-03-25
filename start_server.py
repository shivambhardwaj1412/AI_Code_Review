"""
start_server.py
---------------
Starts the FastAPI server and opens a pyngrok HTTPS tunnel.
Run: python start_server.py

After startup it prints:
  ✅ Ngrok URL: https://xxxx.ngrok-free.app
Set that URL + /webhook as your GitHub webhook payload URL.
"""
import os
import sys
import threading
import uvicorn
from dotenv import load_dotenv

load_dotenv()


def start_ngrok(port: int):
    try:
        from pyngrok import ngrok, conf

        ngrok_token = os.getenv("NGROK_AUTHTOKEN", "")
        if ngrok_token:
            conf.get_default().auth_token = ngrok_token

        tunnel = ngrok.connect(port, "http")
        public_url = tunnel.public_url
        print("\n" + "=" * 60)
        print(f"  ✅ Ngrok tunnel active!")
        print(f"  🌐 Public URL : {public_url}")
        print(f"  🔗 Webhook URL: {public_url}/webhook")
        print("=" * 60)
        print("  👉 Go to your GitHub repo → Settings → Webhooks")
        print(f"     Payload URL : {public_url}/webhook")
        print("     Content type: application/json")
        print(f"     Secret      : {os.getenv('GITHUB_WEBHOOK_SECRET','mysecretkey123')}")
        print("     Events      : Pull requests")
        print("=" * 60 + "\n")
        return public_url
    except Exception as e:
        print(f"  ⚠️  Ngrok failed: {e}")
        print("  ℹ️  Server still running at http://localhost:8000")
        return None


if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 8000))

    # Start ngrok in a thread so uvicorn can start right after
    t = threading.Thread(target=start_ngrok, args=(PORT,), daemon=True)
    t.start()
    t.join(timeout=5)  # wait up to 5s for URL to print

    print(f"\n🚀 Starting FastAPI server on port {PORT}...\n")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False, log_level="info")
