import json

from pymongo import MongoClient
from flask import Flask, render_template, request, redirect, url_for
import chess
from chess import pgn

from explorer import Explorer, Trainer

explorer = Explorer("user")
trainer = Trainer("user")

app = Flask(__name__)
board = chess.Board()

@app.route("/")
def main():
    return redirect(url_for('repertoire'))


@app.route("/repertoire")
def repertoire():
    return render_template('index.html')

@app.route("/opening", methods=['POST'])
def opening():
    db = explorer.db

    if "opening" in request.form:
        explorer.opening = {"name": request.form["opening"], "color": request.form["color"]}
        trainer.change_opening(explorer.opening)
        return json.dumps(explorer.candidate_moves)

    if "name" in request.form:
        form_name = request.form["name"]
        form_color = request.form["color"]

        exists = db["opening"].find_one({"name": form_name, "color": form_color})
        if not exists:
            new_id = db.opening.count()+1
            db["opening"].insert_one({"name": form_name, "color": form_color, "id": new_id})

    white = db["opening"].find({"color": "White"})
    black = db["opening"].find({"color": "Black"})
    result = dict()
    result["white"] = [o["name"] for o in white]
    result["black"] = [o["name"] for o in black]
    return json.dumps(result)

@app.route("/training", methods=['GET'])
def training():
    return render_template('training.html')


@app.route("/positions", methods=['POST'])
def positions():
    if "load" in request.form:
        board, move = trainer.random_position()
        return json.dumps((board["fen"], move["move"]))

@app.route("/moves",  methods=['POST'])
def moves():
    result = dict()
    if "previous" in request.form:
        explorer.previous()
        result["candidates"] = explorer.candidate_moves
        return json.dumps(result)
    elif "next" in request.form:
        notation = explorer.next()
        result["move"] = notation
        result["candidates"] = explorer.candidate_moves
        return json.dumps(result)
    elif ("new[source]" in request.form and
          "new[target]" in request.form):
        source = request.form.get("new[source]")
        target = request.form.get("new[target]")
        move = chess.Move.from_uci(source+target)
        notation = explorer.push(move)    
        result["move"] = notation
        result["candidates"] = explorer.candidate_moves
        return json.dumps(result)

def import_pgn(pgn_file):
    with open(pgn_file) as pgn_f:
        game = pgn.read_game(pgn_f)
    return game

if __name__ == "__main__":
    app.run()
    #game = import_pgn("spain.pgn")
    #explorer = Explorer("jan")
    #for m in game.main_line():
    #    explorer.push(m)
