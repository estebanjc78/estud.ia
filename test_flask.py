from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hola Esteban, Flask está vivo 🚀"

if __name__ == "__main__":
    app.run(debug=True)
