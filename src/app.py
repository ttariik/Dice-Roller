from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
@app.route("/<string:name>")
def hello_world(name: str = None) -> str:
    return render_template("index.html" , _name=name)


@app.route("/dices")
def show_dices() -> str:
    return "Look at these beautiful dices"
