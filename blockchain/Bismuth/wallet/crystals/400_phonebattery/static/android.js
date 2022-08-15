// Storage for asset data
var asset_data;
var plottype_desc = ["Line", "Line (Filled)", "Bar"];
var plottype_opt = ["line","line","bar"];
var plotoptions_desc = ["Battery Level (%)", "Current (mA)", "Temperature","Number of Battery Cycles"];
var plotoptions_opt = ["percentage", "current", "temperature","battery_cycles"];
var tablevar_desc = ["Battery Level (%)", "Current (mA)", "Temperature", "Phone Status", "Phone Health", "Plugged", "Number of Battery Cycles", "Monthly Battery Cycles"];
var tablevar_opt = ["percentage", "current", "temperature", "status", "health", "plugged", "battery_cycles", "monthly_cycles"];
var temperature_desc = ["Celsius","Fahrenheit"];
var temperature_opt = ["C","F"];
var PDFOptions_desc = ["A4 + Portrait", "A4 + Landscape", "US Legal + Portrait", "US Legal + Landscape"];
var PDFOptions_opt = ["1","2","3","4"];

// Start of function declarations

function display_mode(mode) {
    //Defines Day or Night Mode
    localStorage.setItem("phone_mode",mode);
    if(mode == "Day") {
        var bg = "#ffffff";
        var bg_card = "#eeeeee";
        var fg = "#000000";
    } else {
        var bg = "#192035";
        var bg_card = "#202940";
        var fg = "#8b92a9";
    }
    document.body.style.background = bg;

    var elements = document.getElementsByClassName("card");
    for (var i = 0; i < elements.length; i++) {
        elements[i].style.backgroundColor=bg_card;
    }
    var elements = document.getElementsByClassName("input");
    for (var i = 0; i < elements.length; i++) {
        elements[i].style.backgroundColor=bg_card;
    }
    var elements = document.getElementsByClassName("card-body");
    for (var i = 0; i < elements.length; i++) {
        elements[i].style.color=fg;
    }
}

function getColors() {
    out = "style='background-color:#202940;color:#8b92a9;'";
    mode = localStorage.getItem("phone_mode");
    if(mode == "Day") {
        out = "style='background-color:#eeeeee;color:#000000;'";
    }
    return out;
}

function getbgColor() {
    out = "#202940;";
    mode = localStorage.getItem("phone_mode");
    if(mode == "Day") {
        out = "#eeeeee;";
    }
    return out;
}

function FetchID() {
    //Fetches asset ID number and displays in $('#asset_id')
    var xsrf = $("[name='_xsrf']").val();
    localStorage.setItem("phone_pwd", $("#phone_pwd").val());
    var pwd = $('#phone_pwd').val();

    $.post('fetch_asset_id', { pwd: pwd, _xsrf: xsrf }, function(text){
        text = text.replace(/&#39;/g,'"');
        text = text.replace(/&quot;/g,'"');
        var data = JSON.parse(text);
        if(data.count>0) {
            $('#asset_id').html('');
            for(i=0; i<data.count; i++) {
                value = data.phone[i];
                $('#asset_id').append($('<option>').text(value).attr('value', value));
            }
            var x = document.getElementById("div_reg");
            x.style.display = "block";
        } else {
            message_post('Android Phone','No Android asset ID found. You need to have the Termux API installed.','warning');
        }
    });
}

function temperature(celsius) {
    //Displays temperatature (C or F) in localStorage 'phone_temperature'
    var temperature = getLocal("phone_temperature",temperature_opt[0]);
    var out = celsius;
    if(temperature == "F") {
        out = celsius_to_fahrenheit(celsius);
    }
    return out;
}

function updateHTML(asset_id) {
    //Displays asset API data on Page2
    try {
        var current = asset_data[asset_id].current/1000;
        var ts = new Date(asset_data[asset_id].timestamp);
        $("#phone_percentage").html(asset_data[asset_id].percentage);
        $("#phone_current").html(current);
        $("#phone_health").html(asset_data[asset_id].health);
        $("#phone_status").html(asset_data[asset_id].status);
        $("#phone_plugged").html(asset_data[asset_id].plugged);
        $("#phone_temp").html(temperature(asset_data[asset_id].temperature));
        $("#timestamp").html(ts.toLocaleString());
    } catch(e) {
    }
}

function dataSubmit() {
    //Submit phone:battery data to chain
    var xsrf = $("[name='_xsrf']").val();
    var address = "Bis1QPHone8oYrrDRjAFW1sNjyJjUqHgZhgAw";
    var operation = "phone:battery";
    var data = asset_data;
    delete(data.total);
    var out = JSON.stringify(data);
    var asset_id = $("#selectBox option:selected").text();

    //If the account can unregister, it can also submit data
    $.post('check_id_unregister', { asset_id: asset_id, _xsrf: xsrf }, function(data){
        if(data != -1) {
           send(address, 1.0, operation, out);
        } else {
           message_post("Data submission not possible.","Check if the current wallet address has previously registered this ID: " + asset_id,"warning");
        }
    });
}

function FetchPhoneData() {
    //Fetches phone data and stores in variable asset_data, updates display on Page2
    var xsrf = $("[name='_xsrf']").val();
    message_post('Android Phone','Fetching battery data using Termux API. Wait a few seconds. If it fails, try again.','info');

    localStorage.setItem("phone_pwd", $("#phone_pwd").val());
    var pwd = $('#phone_pwd').val();

    $.post('fetch_api_data', { pwd: pwd, _xsrf: xsrf }, function(text){
        text = text.replace(/&#39;/g,'"');
        text = text.replace(/&quot;/g,'"');
        var data = JSON.parse(text);
        if(data.total>0) {
            var html = "<select id='selectBox' class='form-control' onChange='changeFunc();' style='color:#888888'>";
            for(i=0; i<data.total; i++) {
                value = data.asset_id[i];
                html = html.concat("<option value='", value, "'>", value, "</option>");
            }
            html = html.concat("</select>");
            $("#p_selectBox").html(html);
            asset_data = data;
            changeFunc();
        }
    });
}

function RegisterPhone() {
    //Registers the phone ID number on chain, if no one else has done it previously
    var to = "Bis1QPHone8oYrrDRjAFW1sNjyJjUqHgZhgAw";
    var operation = "phone:register";
    var asset_id = document.getElementById("asset_id").value
    var xsrf = $("[name='_xsrf']").val();
    $.post('check_id_register', { asset_id: asset_id, _xsrf: xsrf }, function(data){
        if(data != -1) {
           send(to, 5.0, operation, asset_id);
        } else {
           message_post("Invalid asset ID or already registered.",asset_id,"warning");
        }
    });
}

function UnregisterPhone() {
    //Unregisters the phone ID number to allow others to take it over
    var to = "Bis1QPHone8oYrrDRjAFW1sNjyJjUqHgZhgAw";
    var operation = "phone:unregister";
    var asset_id = document.getElementById("asset_id").value
    var xsrf = $("[name='_xsrf']").val();
    $.post('check_id_unregister', { asset_id: asset_id, _xsrf: xsrf }, function(data){
        if(data != -1) {
           send(to, 0.0, operation, asset_id);
        } else {
           message_post("Unregister not possible.","Check if the current wallet address has previously registered asset ID: " + asset_id,"warning");
        }
    });

}

function changeFunc() {
    //Updates table on Page2
    var asset_id = $("#selectBox option:selected").text();
    updateHTML(asset_id);
    $("#table1").show();
}

function updateLocalStorage() {
    //Stores user input selections in localStorage
    localStorage.setItem("phone_startdate", $("#startdate").val());
    localStorage.setItem("phone_enddate", $("#enddate").val());
    localStorage.setItem("phone_pdfimage", $("#pdf_image").val());
}

function showTable() {
    //Fetches asset data for a given ID and displays DataTable on Page3
    var xsrf = $("[name='_xsrf']").val();
    var variable = getLocal("phone_tablevar",tablevar_opt[0]);
    var variable_desc = getLocal("phone_tablevar_desc",tablevar_desc[0]);
    var temperature = getLocal("phone_temperature",temperature_opt[0]);
    var pdfoptions = getLocal("phone_PDFOptions",PDFOptions_opt[0]);
    var pdfoptions_desc = getLocal("phone_PDFOptions_desc",PDFOptions_desc[0]);

    var selected_id = $("#selected_id").val().split(",");
    var asset_id = selected_id[0];
    var address = selected_id[1];

    var pdfimage = $("#pdf_image").val();
    var d0 = $("#startdate").val();
    var d1 = $("#enddate").val();
    var mysum = 0.0;

    if(asset_id.length>0) {
        if(variable_desc == "Temperature") {
            variable_desc = variable_desc + " (deg " + getLocal("phone_temperature",temperature_opt[0]) + ")";
        }

        var orientation = "portrait";
        var pageSize = "A4";
        if((pdfoptions == 2) || (pdfoptions == 4)) {
            orientation = "landscape";
        }
        if((pdfoptions == 3) || (pdfoptions == 4)) {
            pageSize = "LEGAL";
        }
        updateLocalStorage();
        $(".content").css({"cursor":"wait"});
        $('#table1').DataTable().clear().destroy();
        $('#table1').show();

        var img = new Image();
        img.onload = function(){
            var ctx = $("#canvas")[0].getContext("2d");
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);
            var dataURL = $("#canvas")[0].toDataURL();
            var table = $('#table1').DataTable({"pageLength": 25, dom: 'Bfrtip', buttons: [ { extend: 'pdfHtml5', orientation: orientation, pageSize: pageSize, title: 'Asset ID: ' + asset_id, customize: function ( doc ) { doc.content.splice( 1, 0, { margin: [ 0, 0, 0, 12 ], alignment: 'center', image: dataURL });} }, { extend: 'csvHtml5', title: asset_id } ], retrieve: true, columnDefs: [{ targets: -1, className: 'dt-body-right' } ] });

            $.post('get_chain_data', { asset_id: asset_id, address: address, variable: variable, temperature: temperature, startdate: d0, enddate: d1, _xsrf: xsrf }, function(text){
                text = text.replace(/&#39;/g,'"');
                text = text.replace(/&quot;/g,'"');
                var data = JSON.parse(text);
                var xname = table.column(0).header();
                var column = table.column(1).header();
                if(variable == "battery_cycles") {
                    $(xname).html("Cycle Percentage Levels");
                } else {
                    $(xname).html("Date/Time");
                }
                $(column).html(variable_desc);
                for(i=0; i<data.x.length; i++) {
                    table.row.add([data.x[i], data.y[i]]);
                    if(i==0) {
                        mysum = data.y[0];
                    } else {
                        if(data.y[i] != data.y[i-1]) { mysum += data.y[i]; }
                    }
                }
                if(variable_desc.search("Sum") == 0) {
                    table.row.add([d1 + " (Sum)", mysum]);
                } else if(variable == "battery_cycles") {
                    if(data.x.length>0) {
                        table.row.add(["Full Cycle Equivalent", data.full_cycle_equivalent]);
                    }
                }
                table.draw();
                $('#table2 td').css('background-color',getbgColor());
                $(".content").css({"cursor":"default"});
            });
        }
        var imgFile = "static/" + pdfimage;
        if(fileExists(imgFile)) {
            img.src = imgFile;
        } else {
            img.src = "static/pdflogo.png";
        }
    }
}

function radioClick(id_array,desc,val,i,N) {
    var id = id_array.split(",");
    localStorage.setItem(id[0], desc);
    localStorage.setItem(id[1], val);
    for(j=0; j<N; j++) {
        if(j!=i) {
            tag = "#" + id[1] + "_" + j;
            $(tag).prop("checked", false);
        }
    }
    changeFunc();
}

function getLocal(id,def) {
    var out = def;
    try {
        out = localStorage.getItem(id);
        if(!out) { out=def };
    } catch(e) {}
    return out;
}

function radio(desc,vals,id) {
    var N = vals.length;
    var out = "";
    for(i=0; i<N; i++) {
        var checked = "";
        if(desc[i] == getLocal(id[0],desc[0])) {
            checked = " checked='checked'";
        }
        out = out + "<input type='radio' id='" + id[1] + "_" + i + "' onclick='radioClick(" + '"' + id + '","' + desc[i] + '","' + vals[i] + '",' + i + "," + N + ");'" + checked + ">&nbsp;" + desc[i] + "<br/>";
    }
    return out;
}

function search_asset_ids() {
    //Searches for all asset ids on chain and displays menu on Page3
    var xsrf = $("[name='_xsrf']").val();
    var asset_search = $("#asset_search").val();

    $.post('get_all_asset_ids', { asset_search: asset_search, _xsrf: xsrf }, function(text){
        text = text.replace(/&#39;/g,'"');
        text = text.replace(/&quot;/g,'"');
        var data = JSON.parse(text);
        if(data.total>0) {
            var html = ("<div><div class='cell'><div class='cell-overflow'>");
            html = html.concat("<table id='table2' ", getColors(), "><thead><tr><th>Asset ID</th><th>Address</th></tr></thead></table></div></div>");
            html = html.concat("<br/><table><tr><td>Selected ID:&nbsp;</td><td><input type='text' size='10' id='selected_id' readonly ", getColors(), "></td></tr>");
            html = html.concat("<tr><td>Start Date:&nbsp;</td><td><input type='text' size='10' readonly='true' value='", localStorage.getItem("phone_startdate"), "' id='startdate'");
            html = html.concat(" onClick='pickDate($(this));' ", getColors(), "'>");
            html = html.concat("</td></tr><tr><td>End Date:</td><td><input type='text' size='10' value='", today(), "' readonly='true' id='enddate'");
            html = html.concat(" onClick='pickDate($(this));' ", getColors(), "'>");
            html = html.concat("</td></tr></table><br/><table width='100%'><tr><td width='50%'>");
            html = html.concat("Show Temperature As:&nbsp;&nbsp;&nbsp;<br/>", radio(temperature_desc,temperature_opt,["phone_temperature_desc","phone_temperature"]), "<br/>");
            html = html.concat("Select Plot Variable:<br/>", radio(plotoptions_desc,plotoptions_opt,["phone_plotoptions_desc", "phone_plotoptions"]), "<br/>");
            html = html.concat("Plot Type:<br/>", radio(plottype_desc,plottype_opt,["phone_plottype_desc", "phone_plottype"]), "<br/>");
            html = html.concat("<button onclick='plotData();' class='btn btn-secondary'>Show Plot</button>");
            html = html.concat("</td><td width='50%'>");
            html = html.concat("Select Table Variable:");
            html = html.concat("<br/>", radio(tablevar_desc,tablevar_opt,["phone_tablevar_desc", "phone_tablevar"]), "<br/>");
            html = html.concat("PDF Format:<br/>", radio(PDFOptions_desc,PDFOptions_opt,["phone_PDFOptions_desc", "phone_PDFOptions"]), "<br/>");
            html = html.concat("PDF Image File (stored in wallet/crystals/400_phonebattery/static): <input type='text' value='", localStorage.getItem("phone_pdfimage"), "' id='pdf_image' class='form-control'", getColors(), ">");
            html = html.concat("<button onclick='showTable();' class='btn btn-secondary'>Show Table</button>");
            html = html.concat("</td></tr></table></div>");
            $("#p_selectBox").html(html);

            $(".content").css({"cursor":"wait"});
            $('#table2').DataTable().clear().destroy();
            $('#table2').show();
            var table = $('#table2').DataTable({"info": false});
            for(i=0; i<data.total; i++) {
                asset_id = data.asset_id[i];
                address = data[asset_id].address;
                table.row.add([asset_id, address]);
            }
            table.draw();
            $('#table2 td').css('background-color',getbgColor());
            var row = table.rows({selected:true}).data();
            if(row[0].length>0) {
                $('#selected_id').val(row[0]);
            }
            try {
                if(localStorage.getItem("phone_selected_id").length>0) {
                    $('#selected_id').val(localStorage.getItem("phone_selected_id"));
                }
            } catch(e) {}
            $('#table2 tbody').on('click', 'tr', function () { $('#selected_id').val(table.row(this).data()); localStorage.setItem('phone_selected_id',$('#selected_id').val()); });
            $(".content").css({"cursor":"default"});
        }
    });
}

function plotData() {
    //Fetches asset data for a given ID and displays ChartJS plot on Page3
    var xsrf = $("[name='_xsrf']").val();
    var variable = getLocal("phone_plotoptions",plotoptions_opt[0]);
    var variable_desc = getLocal("phone_plotoptions_desc",plotoptions_desc[0]);
    var plottype = getLocal("phone_plottype",plottype_opt[0]);
    var plot_desc = getLocal("phone_plottype_desc",plottype_desc[0]);
    var temperature = getLocal("phone_temperature",temperature_opt[0]);
    var selected_id = $("#selected_id").val().split(",");
    var asset_id = selected_id[0];
    var address = selected_id[1];
    var d0 = $("#startdate").val();
    var d1 = $("#enddate").val();

    if(variable_desc == "Temperature") {
        variable_desc = variable_desc + " (deg " + getLocal("phone_temperature",temperature_opt[0]) + ")";
    }
    updateLocalStorage();

    if(asset_id.length>0) {
        $.post('get_chain_data', { asset_id: asset_id, address: address, variable: variable, temperature: temperature, startdate: d0, enddate: d1, _xsrf: xsrf }, function(text){
            text = text.replace(/&#39;/g,'"');
            text = text.replace(/&quot;/g,'"');
            var data = JSON.parse(text);
            var x = new Array();
            var y = new Array();
            var xy = new Array();
            for(i=0; i<data.x.length; i++) {
                x.push(data.x[i]);
                y.push(data.y[i]);
                xy.push({"x": data.x[i], "y": data.y[i]});
            }
            $('#myChart').remove();
            $('#div_plot').append('<canvas id="myChart"><canvas>');
            var ctx = $('#myChart').get(0).getContext('2d');
            var col = "rgba(77,166,83,1.0)";
            var fill = false;
            if(variable == "battery_cycles") {
                plottype = "bar";
            }
            if(plot_desc.indexOf("Fill") >= 0) { fill = true; }
            var options = { "scales": { "xAxes": [{ "ticks": { "autoSkip": true, "maxRotation": 90, "minRotation": 90 } }] } }
            var chart = new Chart(ctx,{"type":plottype,"data":{"labels": x ,"datasets":[{"label":variable_desc,"backgroundColor":col,"data": y,"fill":fill, "pointRadius": 4, "borderColor":"gray"}]},"options": options});
        });
    }
};
