// Opening Tree Viewer

var defaultData = [
          {
            text: 'White',
            href: '#white',
            selectable: false,
          },
          {
            text: 'Black',
            href: '#black',
            selectable: false,
          }
        ];

$.ajax({
      type: "POST",
      url: "/opening",
      dataType: 'json',
      success: function(response) {
          console.log(response);
          init_tree(response);
      },
      error: function(error) {
          console.log(error);
      }
    });


var init_tree = function(openings) {
    var white = openings["white"];
    var black = openings["black"];

    defaultData[0]["nodes"] = [];
    defaultData[1]["nodes"] = [];
    for(var i=0;i<white.length;i++){
        var node = {"text": white[i]};
        defaultData[0]["nodes"].push(node);
    }
    for(var i=0;i<black.length;i++){
        var node = {"text": black[i]};
        defaultData[1]["nodes"].push(node);
    }
    $('#Opening_Explorer').treeview({
        data: defaultData,
        'onNodeSelected': node_selected,
    });
};

var node_selected =  function(event, data) {
    $('#selected_opening').text(data["text"]);
    var parent = $('#Opening_Explorer').treeview('getNode', data["parentId"]);
    var send = {"opening": data["text"], "color": parent["text"]};
    
    $.ajax({
      type: "POST",
      url: "/opening",
      dataType: 'json',
      data: $.param(send),
      success: function(response) {
          console.log(response);
          showCandidateMoves(response);
          board.orientation(parent["text"].toLowerCase());
      },
      error: function(error) {
          console.log(error);
      }
    });
}

$('#opening_form').submit(function(event){
    // cancels the form submission
    event.preventDefault();
    var data = {"color": $("#opening_color").val(), "name": $("#new_opening_name").val()};
    $.ajax({
      type: "POST",
      url: "/opening",
      data: $.param(data),
      dataType: 'json',
      success: function(response) {
          console.log(response);
          init_tree(response);
      },
      error: function(error) {
          console.log(error);
      }
    });
});

$('#opening_dropdown_icon').parent().on("click", function(e){
    $('#opening_dropdown_icon').toggleClass("glyphicon-menu-down");
    $('#opening_dropdown_icon').toggleClass("glyphicon-menu-up");
});






