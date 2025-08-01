from flask import Flask
from markupsafe import escape

app = Flask(__name__)

@app.route("/")
def hello_world() -> str:
    return "<p>Hello, World!</p>"

@app.route("/<name>")
def personalized_hello(name: str) -> str:
    safe_name = escape(name)
    return f"Hello, {safe_name}"

@app.route("/dices")
def show_dices() -> str:
    return "Look at these beautiful dices"
