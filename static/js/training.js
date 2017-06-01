var board,
    correct_move,
  game = new Chess();

// do not pick up pieces if the game is over
// only pick up pieces for the side to move
var onDragStart = function(source, piece, position, orientation) {
  if (game.game_over() === true ||
      (game.turn() === 'w' && piece.search(/^b/) !== -1) ||
      (game.turn() === 'b' && piece.search(/^w/) !== -1)) {
    return false;
  }
};

var onDrop = function(source, target) {
  // see if the move is legal
  var move = game.move({
    from: source,
    to: target,
    promotion: 'q' // NOTE: always promote to a queen for example simplicity
  });

  // illegal move
  var san = move["from"]+move["to"];

  if (san !== correct_move){
    wrongMove(san);
    return 'snapback';
  }
  if (move === null) return 'snapback';

  correctMove(san);
  //sendMove(source, target);
};

// update the board position after the piece snap 
// for castling, en passant, pawn promotion
var onSnapEnd = function() {
  board.position(game.fen());
};

var sendMove = function(source, target) {
    var moves = {"new": {"source" : source, "target" : target}};

    $.ajax({
      type: "POST",
      url: "/moves",
      data: $.param(moves),
      dataType: 'json',
      success: function(response) {
          console.log(response);
          updateMoveList(response);
      },
      error: function(error) {
          console.log(error);
      }
    });
};

var wrongMove = function(move) {
    game.undo();
    $("#status").text("Wrong");
};

var correctMove = function(move) {
    $("#status").text("Correct");
    $("#training_load_position").click();
};

var updateMoveList = function(response) {
    var turn = Math.floor(game.history().length/2 - 0.5)+1;
    if (game.turn() === 'b') {
        var td = "<td id='white_"+turn+"'>"+turn+". "+response["move"]+"</td>";
        var result = "<tr id='turn_"+turn+"'>";
        result = result+td;
        result = result + "</tr>";
        $("#pgn-table").append(result);
    }
    else{
        var td = "<td id='black_"+turn+"'>"+response["move"]+"</td>";
        $("#turn_"+turn).append(td);
    }
}

var showCandidateMoves = function(response){

};

var cfg = {
  draggable: true,
  position: 'start',
  onDragStart: onDragStart,
  onDrop: onDrop,
  onSnapEnd: onSnapEnd
};
board = ChessBoard('board', cfg);


var load_position = function(event){
    var send = {"load": "random"};
    $.ajax({
      type: "POST",
      url: "/positions",
      dataType: 'json',
      data: $.param(send),
      success: function(response) {
          var fen = response[0];
          correct_move = response[1];
          if(game.load(fen)){
            board.position(fen);
          }
          console.log(response);
      },
      error: function(error) {
          console.log(error);
      }
    });
}


$("#training_load_position").on("click", load_position);
