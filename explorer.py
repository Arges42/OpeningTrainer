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
        self.color = fen.split(" ")[1]

    def next(self, move):
        pass

    def candidate_moves(self, db, opening=None):
        find = {"board_start": self.board_id}
        if not opening is None:
            find["opening"] = opening
        moves = db.moves.find(find)
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
        self.opening = opening

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


class VariationTree:
    def __init__(self, moves=None, positions=None):
        if not (moves is None or positions is None):
            self._build_graph(moves, positions)

    def traverse(self, start=0):
        nodes = []
        edges = []
        stack = [start]
        while stack:
            cur_node = stack[0]
            stack = stack[1:]
            nodes.append(self.nodes[cur_node])
            if cur_node in self.adjaceny_list:
                for child in self.adjaceny_list[cur_node]:
                    stack.insert(0, child)
        return self._positions_to_moves(nodes)

    def _positions_to_moves(self, positions):
        for i in range(len(positions)-1):
            start_pos = positions[i].board_id
            end_pos = positions[i+1].board_id
            try:
                yield positions[i], self.moves[str(start_pos)+"-"+str(end_pos)]
            except:
                continue

    def _build_graph(self, moves, positions):
        if not isinstance(moves, Move):
            moves = Move.from_mongodb(moves)
        if not isinstance(positions, BoardNode):
            positions = BoardNode.from_mongodb(positions)
        
        self.adjaceny_list = dict()
        self.moves = dict()
        for move in moves:
            self.moves[str(move.from_id)+"-"+str(move.to_id)] = move
            if move.from_id in self.adjaceny_list:
                self.adjaceny_list[move.from_id].add(move.to_id)
            else:
                self.adjaceny_list[move.from_id] = set([move.to_id])

        self.nodes = dict()
        for pos in positions:
            self.nodes[pos.board_id] = pos


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
        self._color = True

    def random_position(self):
        move = random.sample(list(self.db.moves.find({"opening": self.opening, "color": self._color})), 1)[0]
        board = self.db.positions.find_one({"BoardId": move["board_start"]})
        return board, move

    def complete_opening(self):
        moves = self.db.moves.find({"opening": self.opening})
        pos_ids = list(set(moves.distinct("board_start")).union(set(moves.distinct("board_end"))))
        positions = self.db.positions.find({"BoardId": {"$in":pos_ids}})
        tree = VariationTree(moves, positions)
        self.variations = tree.traverse()

    def next(self):
        try:
            board, move = next(self.variations)
            while board.color != self.color:                
                board, move = next(self.variations)                
            return board, move
        except StopIteration:
            return None, None      

    def change_opening(self, opening):
        self.opening = opening
        self._query_opening()
    
    @property
    def color(self):
        if self._color:
            return "b"
        else:
            return "w"

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
            self.board = self._starting_position()

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
        candidates = {"major": [], "minor": []}
        chess_board = chess.Board(self.board.fen)
        for move in self.board.candidate_moves(self.db):
            if self.opening in move.opening:
                candidates["major"].append(chess_board.san(chess.Move.from_uci(move.uci)))
            else:
                candidates["minor"].append(chess_board.san(chess.Move.from_uci(move.uci)))

        return candidates

