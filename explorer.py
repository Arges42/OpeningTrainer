import random

import pymongo
from pymongo import MongoClient

import chess
from chess import pgn


class OpeningTrainerError(Exception):
    """Base class for exceptions in this module."""
    pass

class OpeningNotFoundError(OpeningTrainerError):
    """Exception raised for openings that could not be found
    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, expression, message):
        self.expression = expression
        self.message = message


class BoardNode:
    def __init__(self, fen, board_id):
        self.fen = fen
        self.board_id = board_id

    def next(self, move):
        pass

    def candidate_moves(self, db):
        moves = db.moves.find({"board_start": self.board_id})
        return Move.from_mongodb(moves)

    @staticmethod
    def from_mongodb(positions):
        for pos in positions:
            yield BoardNode(pos["fen"], pos["BoardId"])        

class Move:
    def __init__(self, uci, from_id, to_id, opening=[]):
        self.uci = uci
        self.from_id = from_id
        self.to_id = to_id
        self.opening = list()

    @staticmethod
    def from_mongodb(query_result):
        for move in query_result:
            yield Move(move["move"],
                       move["board_start"],
                       move["board_end"],
                       move["opening"])

    def execute(self, db):
        pos = db.positions.find({"BoardId": self.to_id})
        return next(BoardNode.from_mongodb(pos))

    def undo(self, db):
        pos = db.positions.find({"BoardId": self.from_id})
        return next(BoardNode.from_mongodb(pos))

class History:
    def __init__(self, db):
        self._moves = list()
        self._index = -1
        self._db = db

    def execute(self, move):
        self._moves = self._moves[:(self._index+1)]
        self._moves.append(move)
        board = move.execute(self._db)
        self._index = len(self._moves)-1
        return board

    def undo(self):
        board = self._moves[self._index].undo(self._db)
        self._index -= 1
        return board

    def redo(self):
        self._index += 1
        move = self._moves[self._index]
        board = move.execute(self._db)
        return move, board

class Trainer:    
    def __init__(self, user):
        client = MongoClient()
        self.db = client[user]
        self.opening = -1
        self._color = "White"

    def random_position(self):
        move = random.sample(list(self.db.moves.find({"opening": self.opening, "color": self._color})), 1)[0]
        board = self.db.positions.find_one({"BoardId": move["board_start"]})
        return board, move

    def change_opening(self, opening):
        self.opening = opening
        self._query_opening()

    def _query_opening(self):
        result = self.db.opening.find_one({"id": self.opening})
        try:
            if result["color"] == "White":
                self._color = False
            else:
                self._color = True
        except Exception as err:
            print(err)


class Explorer:
    """ This class is aware of the current board state, aswell as the boardId.
        The class primary focus is to return all candidate moves 
        for the current position.
    """
    def __init__(self, user):
        client = MongoClient()
        self.db = client[user]
        
        self.history = History(self.db)
        self._current_board_id = 0
        self.board = self._starting_position()

    def push(self, move):
        """Add a new move to the explorer 
           and check if the occuring position already exists in the db.

        """
        notation = self._notation(move)
        m = self._check_move(move.uci())
        self.board = self.history.execute(m)

        return notation

    def next(self):
        move, new_board = self.history.redo()
        notation = self._notation(chess.Move.from_uci(move.uci))
        self.board = new_board
        return notation

    def previous(self):
        self.board = self.history.undo()

    @property
    def opening(self):
        return self._opening

    @opening.setter
    def opening(self, opening):
        exists = self.db.opening.find_one({"name": opening["name"], "color": opening["color"]})
        if exists:
            self._opening = exists["id"]

    def _starting_position(self):
        """Check if the starting position is in the db, if not insert it."""
        try:
            board = self.db.positions.find({"BoardId": 0})
            return next(BoardNode.from_mongodb(board))
        except StopIteration:
            fen = chess.Board().fen()
            self.db.positions.insert_one({"fen": fen, "BoardId": 0})
            return BoardNode(fen, 0)

    def _notation(self, move):
        """Return the notation of the last move."""
        return chess.Board(self.board.fen).san(move)

    def _check_move(self, move):
        """Check if the move already exists."""
        exists = self.db.moves.find_one({"board_start": self.board.board_id,
                                     "move": move})

        if exists:
            if self._opening in exists["opening"]:
                #FIXME: not very pythonic
                return next(Move.from_mongodb([exists]))
            else:
                self.db.moves.update({"_id": exists["_id"]},{"$addToSet":{"opening": self._opening}})
                exists = self.db.moves.find_one({"board_start": self.board.board_id,
                                             "move": move})
                return next(Move.from_mongodb([exists]))
                
        else: 
            return self._insert_move(move)
            
    def _insert_move(self, move):
        """Insert the move into the db,
           if the resulting position does not exist insert it. 
        """
        chess_board = chess.Board(self.board.fen)
        chess_board.push_uci(move)

        position = self.db.positions.find({"fen": chess_board.fen()})
        try:
            board_node = next(BoardNode.from_mongodb(position))
        except StopIteration:
            board_node = self._insert_position(chess_board.fen())

        self.db.moves.insert_one({"board_start": self.board.board_id,
                                  "board_end": board_node.board_id,
                                  "move": move,
                                  "color": chess_board.turn,
                                  "opening": [self._opening]})

        return Move(move, self.board.board_id, board_node.board_id, self._opening)
    
    def _insert_position(self, fen):
        """Insert a new position into the db."""
        max_board_id = self.db.positions.find_one(
                        sort=[("BoardId", pymongo.DESCENDING)]
                       )
        max_board_id = max_board_id["BoardId"]+1
        self.db.positions.insert_one({"fen": fen,
                                      "BoardId": max_board_id})
        return BoardNode(fen, max_board_id)



    @staticmethod
    def import_pgn(pgn_file):
        pass

    @property
    def candidate_moves(self):
        candidates = []
        chess_board = chess.Board(self.board.fen)
        for move in self.board.candidate_moves(self.db):
            candidates.append(chess_board.san(chess.Move.from_uci(move.uci)))

        return candidates

