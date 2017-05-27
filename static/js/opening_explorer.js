// Opening Tree Viewer

var defaultData = [
          {
            text: 'White',
            href: '#white',
          },
          {
            text: 'Black',
            href: '#black',
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
    });
};

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




