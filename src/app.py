from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def hello_world() -> str:
    return render_template("index.html")

@app.route("/<name>")
def personalized_hello(name: str) -> str:
    return render_template("index.html", _name=name)

@app.route("/dices")
def show_dices() -> str:
    return "Look at these beautiful dices"
