// This script contains general utility functions in js which can be useful for any crystal dev
// GH2, 2020-04-22

function message_get(title,msg,type){
    //Submit (get) msg, title and type to message_popup.html and display the result in #message_window
    $.get('message_popup?msg=' + msg + '&title=' + title + '&type=' + type,function(page){
        $("#message_window").html(page);
        $("#message_window").modal("show");
        });
}

function message_post(title,msg,type){
    //Submit (get) msg, title and type to message_popup.html and display the result in #message_window
    var xsrf = $("[name='_xsrf']").val();
    $.post('message_popup', { msg: msg, title: title, type: type, _xsrf: xsrf }, function(page){
        $("#message_window").html(page);
        $("#message_window").modal("show");
    });
}

function today() {
    //Returns today's date on format YYYY-mm-dd
    var today = new Date();
    var dd = String(today.getDate()).padStart(2, '0');
    var mm = String(today.getMonth() + 1).padStart(2, '0');
    var yyyy = today.getFullYear();
    today = yyyy + '-' + mm + '-' + dd;
    return(today);
}

function miles_to_km(x) {
    //Converts miles to kilometers
    var y = x*1.609344;
    y = Math.round(y * 100) / 100; //Two decimals
    return y;
}

function celsius_to_fahrenheit(C) {
    //Converts Celsius to Fahrenheit
    var F = C*1.8 + 32.0;
    F = Math.round(F * 10) / 10; //One decimal
    return(F);
}

function sanitize(data) {
    //Keeps only alphanumeric and dot (.) in the data string, otherwise space
    out = data.replace(/[^0-9a-zA-Z.]/g, ' ');
    return out;
}

function pickDate(d) {
    // Sets date format to YYYY-mm-dd and displays calendar
    d.datepicker({dateFormat: "yy-mm-dd"});
    d.datepicker('show');
}

function checkSelect(a,b) {
    //Compares variable a with localStorage of b and sets variable selected
    selected="";
    if(a==localStorage.getItem(b)) {
        selected="selected ";
    }
    return selected;
}

function select(options,values,local) {
    //Returns an option list with option local selected
    out = "";
    for(i=0; i<options.length; i++) {
        selected=checkSelect(options[i],local);
        out = out.concat("<option ", selected, "value='", values[i], "'>", options[i], "</option>");
    }
    return out;
}

function fileExists(url) {
    if(url){
        var req = new XMLHttpRequest();
        req.open('GET', url, false);
        req.send();
        return req.status==200;
    } else {
        return false;
    }
}

function is_static_available() {
    return 1;
}
