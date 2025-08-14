import os
from flask import Flask, Response
from app.logging_conf import configure_logging  # абсолютний імпорт!

app = Flask(__name__)
configure_logging()  # без аргументів!

@app.route("/healthz")
def healthz():
    return {"status": "ok"}

@app.route("/")
def index():
    return Response("Hello, world!", mimetype="text/plain")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
