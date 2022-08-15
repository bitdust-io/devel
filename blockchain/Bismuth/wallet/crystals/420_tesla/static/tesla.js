// Storage for (multiple) vehicle data
var vehicle_data;
var plottype_desc = ["Line", "Line (Filled)", "Bar"];
var plottype_opt = ["line","line","bar"];
var plotoptions_desc = ["Battery Level (%)", "Usable Battery Level (%)", "Battery Range", "Ideal Battery Range", "Estimated Battery Range", "Last Charge Current Request (A)", "Last Charge Energy Added (kWh)", "Last Charge Range Added Ideal", "Last Charge Range Added Rated", "Inside Temperature", "Outside Temperature", "Odometer", "Estimated Max Range","Estimated Max Range vs. Odometer", "Number of Battery Cycles"];
var plotoptions_opt = ["battery_level", "usable_battery_level", "battery_range", "ideal_battery_range", "est_battery_range", "charge_current_request", "charge_energy_added", "charge_miles_added_ideal", "charge_miles_added_rated", "inside_temp", "outside_temp", "odometer", "est_max_range","max_range_vs_odometer", "battery_cycles"];
var tablevar_desc = ["Estimated Max Range","Car Version","Car Type", "Exterior Color", "Wheel Type", "Sum Charge Energy Added (kWh)","Distance Driven","Number of Battery Cycles","Battery Type","Monthly Distance","Monthly Energy (kWh)","Monthly Efficiency (Wh/mi)","Monthly Battery Cycles"];
var tablevar_opt = ["est_max_range","car_version","car_type","exterior_color","wheel_type","charge_energy_added","odometer","battery_cycles","battery_type","monthly_distance","monthly_energy","monthly_efficiency","monthly_cycles"];
var temperature_desc = ["Celsius","Fahrenheit"];
var temperature_opt = ["C","F"];
var range_desc = ["Kilometers","Miles"];
var range_opt = ["km","mi"];
var PDFOptions_desc = ["A4 + Portrait", "A4 + Landscape", "US Legal + Portrait", "US Legal + Landscape"];
var PDFOptions_opt = ["1","2","3","4"];
var filteroptions_desc = ["1%", "2%", "3%", "4%", "5%", "10%", "15%", "20%", "25%", "All"];
var filteroptions_opt = ["0.99", "0.98", "0.97", "0.96", "0.95", "0.90", "0.85", "0.80", "0.75", "0.0"];

// Start of function declarations

function display_mode(mode) {
    //Defines Day or Night Mode
    localStorage.setItem("tesla_mode",mode);
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
    mode = localStorage.getItem("tesla_mode");
    if(mode == "Day") {
        out = "style='background-color:#eeeeee;color:#000000;'";
    }
    return out;
}

function getbgColor() {
    out = "#202940;";
    mode = localStorage.getItem("tesla_mode");
    if(mode == "Day") {
        out = "#eeeeee;";
    }
    return out;
}

function FetchVIN() {
    //Fetches VIN numbers from Tesla API and displays in $('#vin_input')
    var xsrf = $("[name='_xsrf']").val();
    message_post('Tesla Account','Checking credentials','info');

    email = $("#tesla_email").val();
    pwd = $("#tesla_pwd").val();

    localStorage.setItem("tesla_email", email);
    localStorage.setItem("tesla_pwd", pwd);

    $.post('fetch_asset_id', { pwd: pwd, email: email, _xsrf: xsrf }, function(text){
        text = text.replace(/&#39;/g,'"');
        text = text.replace(/&quot;/g,'"');
        var data = JSON.parse(text);
        if(data.count>0) {
            $('#vin_input').html('');
            for(i=0; i<data.count; i++) {
                value = data.vehicle[i];
                $('#vin_input').append($('<option>').text(value).attr('value', value));
            }
            var x = document.getElementById("div_reg");
            x.style.display = "block";
        } else {
            message_post('Tesla Account','Invalid credentials','warning');
        }
    });
}

function range(miles) {
    //Displays range (miles or km) in $("#range")
    out = miles;
    var range_select = $("#range option:selected").index();
    if(range_select == 0) {
        out = miles_to_km(out);
    }
    return out;
}

function range2(miles) {
    //Displays range (miles or km) in $("#range")
    out = miles;
    var rangeval = getLocal("tesla_range",range_opt[0]);
    if(rangeval == "km") {
        out = miles_to_km(out);
    }
    return out;
}

function temperature(celsius) {
    //Displays temperature (C or F) in $("#temperature")
    var temp_select = $("#temperature option:selected").index();
    out = celsius;
    if(temp_select == 1) {
        out = celsius_to_fahrenheit(celsius);
    }
    return out;
}

function updateHTML(vin) {
    //Displays Tesla API data on Page2
    try {
        var ts = new Date(vehicle_data[vin].timestamp);
        $("#battery_level").html(vehicle_data[vin].battery_level);
        $("#battery_range").html(range(vehicle_data[vin].battery_range));
        $("#usable_battery_level").html(vehicle_data[vin].usable_battery_level);
        $("#charge_current_request").html(vehicle_data[vin].charge_current_request);
        $("#charge_energy_added").html(vehicle_data[vin].charge_energy_added);
        $("#charge_miles_added_ideal").html(range(vehicle_data[vin].charge_miles_added_ideal));
        $("#charge_miles_added_rated").html(range(vehicle_data[vin].charge_miles_added_rated));
        $("#ideal_battery_range").html(range(vehicle_data[vin].ideal_battery_range));
        $("#est_battery_range").html(range(vehicle_data[vin].est_battery_range));
        $("#inside_temp").html(temperature(vehicle_data[vin].inside_temp));
        $("#outside_temp").html(temperature(vehicle_data[vin].outside_temp));
        $("#odometer").html(range(vehicle_data[vin].odometer));
        $("#car_version").html(sanitize(vehicle_data[vin].car_version));
        $("#battery_type").html(vehicle_data[vin].battery_type);
        $("#car_type").html(vehicle_data[vin].car_type);
        $("#exterior_color").html(vehicle_data[vin].exterior_color);
        $("#wheel_type").html(vehicle_data[vin].wheel_type);
        $("#timestamp").html(ts.toLocaleString());
    } catch(e) {
    }
}

function teslaSubmit() {
    //Submit tesla:battery data to chain
    var xsrf = $("[name='_xsrf']").val();
    var address = "Bis1TeSLaWhTC2ByEwZnYWtsPVK5428uqnL46";
    var operation = "tesla:battery";
    var data = vehicle_data;
    delete(data.total);
    var out = JSON.stringify(data);
    var vin_input = $("#selectBox option:selected").text();

    //If the account can unregister, it can also submit data
    $.post('check_vin_unregister', { vin_input: vin_input, _xsrf: xsrf }, function(data){
        if(data != -1) {
           send(address, 1.0, operation, out);
        } else {
           message_post("Data submission not possible.","Check if the current wallet address has previously registered this VIN: " + vin_input,"warning");
        }
    });
}

function FetchVehicleData() {
    //Fetches vehicle data and stores in variable vehicle_data, updates display on Page2
    var xsrf = $("[name='_xsrf']").val();
    message_post('Tesla Account','Checking your credentials and fetching data. Wait typically 10-30 seconds.','info');

    email = $("#tesla_email").val();
    pwd = $("#tesla_pwd").val();
    localStorage.setItem("tesla_email", email);
    localStorage.setItem("tesla_pwd", pwd);
    localStorage.setItem("tesla_range", $("#range option:selected").val());
    localStorage.setItem("tesla_temperature", $("#temperature option:selected").val());

    $.post('fetch_api_data', { email: email, pwd: pwd, _xsrf: xsrf }, function(text){
        text = text.replace(/&#39;/g,'"');
        text = text.replace(/&quot;/g,'"');
        var data = JSON.parse(text);
        if(data.total>0) {
            var html = "<select id='selectBox' class='form-control' onChange='changeFunc();' style='color:#888888'>";
            for(i=0; i<data.total; i++) {
                value = data.vin[i];
                html = html.concat("<option value='", value, "'>", value, "</option>");
            }
            html = html.concat("</select>");
            $("#p_selectBox").html(html);
            vehicle_data = data;
            changeFunc();
        }
    });
}

function RegisterVehicle() {
    //Registers the VIN number on chain, if no one else has done it previously
    var to = "Bis1TeSLaWhTC2ByEwZnYWtsPVK5428uqnL46";
    var operation = "tesla:register";
    var vin_input = document.getElementById("vin_input").value
    var xsrf = $("[name='_xsrf']").val();
    $.post('check_vin_register', { vin_input: vin_input, _xsrf: xsrf }, function(data){
        if(data != -1) {
           send(to, 25.0, operation, vin_input);
        } else {
           message_post("Invalid VIN or already registered.",vin_input,"warning");
        }
    });
}

function UnregisterVehicle() {
    //Unregisters the VIN number to allow others to take it over
    var to = "Bis1TeSLaWhTC2ByEwZnYWtsPVK5428uqnL46";
    var operation = "tesla:unregister";
    var vin_input = document.getElementById("vin_input").value
    var xsrf = $("[name='_xsrf']").val();
    $.post('check_vin_unregister', { vin_input: vin_input, _xsrf: xsrf }, function(data){
        if(data != -1) {
           send(to, 0.0, operation, vin_input);
        } else {
           message_post("Unregister not possible.","Check if the current wallet address has previously registered this VIN: " + vin_input,"warning");
        }
    });

}

function changeFunc() {
    //Updates table on Page2
    var vin = $("#selectBox option:selected").text();
    updateHTML(vin);
    $("#table1").show();
}

function updateLocalStorage() {
    //Stores user input selections in localStorage
    localStorage.setItem("tesla_startdate", $("#startdate").val());
    localStorage.setItem("tesla_pdfimage", $("#pdf_image").val());
}

function showTable() {
    //Fetches vehicle data for a given VIN and displays DataTable on Page3
    var xsrf = $("[name='_xsrf']").val();
    var variable = getLocal("tesla_tablevar",tablevar_opt[0]);
    var variable_desc = getLocal("tesla_tablevar_desc",tablevar_desc[0]);
    var temperature = getLocal("tesla_temperature",temperature_opt[0]);
    var range = getLocal("tesla_range",range_opt[0]);
    var pdfoptions = getLocal("tesla_PDFOptions",PDFOptions_opt[0]);
    var pdfoptions_desc = getLocal("tesla_PDFOptions_desc",PDFOptions_desc[0]);

    var selected_id = $("#selected_id").val().split(",");
    var asset_id = selected_id[0];
    var address = selected_id[1];

    var pdfimage = $("#pdf_image").val();
    var d0 = $("#startdate").val();
    var d1 = $("#enddate").val();
    var mysum = 0.0;

    if(variable_desc.indexOf("Temperature")>=0) {
        variable_desc = variable_desc + " (deg " + getLocal("tesla_temperature",temperature_opt[0]) + ")";
    } else if((variable_desc.indexOf("Distance")>=0) || (variable_desc.indexOf("Range")>=0)) {
        variable_desc = variable_desc + " (" + getLocal("tesla_range",range_opt[0]) + ")";
    }

    orientation = "portrait";
    pageSize = "A4";
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

    img = new Image();
    img.onload = function(){
        var ctx = $("#canvas")[0].getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        var dataURL = $("#canvas")[0].toDataURL();
        var table = $('#table1').DataTable({"pageLength": 25, dom: 'Bfrtip', buttons: [ { extend: 'pdfHtml5', orientation: orientation, pageSize: pageSize, title: 'Vehicle: ' + asset_id, customize: function ( doc ) { doc.content.splice( 1, 0, { margin: [ 0, 0, 0, 12 ], alignment: 'center', image: dataURL });} }, { extend: 'csvHtml5', title: asset_id } ], retrieve: true, columnDefs: [{ targets: -1, className: 'dt-body-right' } ] });

        $.post('get_chain_data', { vin: asset_id, address: address, variable: variable, range: range, temperature: temperature, startdate: d0, enddate: d1, _xsrf: xsrf }, function(text){
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
                table.row.add([d1 + " 23:59:59 (Sum)", mysum]);
            } else if(variable_desc.search("Distance") == 0) {
                distance = data.y[data.y.length-1] - data.y[0];
                table.row.add([d1 + " 23:59:59 (Total Distance)", distance.toFixed(3)]);
            } else if(variable == "battery_cycles") {
                if(data.x.length>0) {
                    table.row.add(["Full Cycle Equivalent", data.full_cycle_equivalent]);
                }
            }
            table.draw();
            $(".content").css({"cursor":"default"});
        });
    }
    imgFile = "static/" + pdfimage;
    if(fileExists(imgFile)) {
        img.src = imgFile;
    } else {
        img.src = "static/pdflogo.png";
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
        out = out + "<input type='radio' id='" + id[1] + "_" + i + "' onclick='radioClick(" + '"' + id + '","' + desc[i] + '","' + vals[i] + '",' + i + "," + N + ");'" + checked + ">&nbsp;" + desc[i];
        if(id[1] != "tesla_filteroptions") {
            out = out + "<br/>";
        } else {
            out = out + "&nbsp;";
            if(i==4) {
                out = out + "<br/>";
            }
        }
    }
    return out;
}

function searchVehicles() {
    //Searches for all vehicles on chain and displays menu on Page3
    var xsrf = $("[name='_xsrf']").val();
    var asset_search = $("#asset_search").val();

    $.post('get_all_asset_ids', { asset_search: asset_search, _xsrf: xsrf }, function(text){
        text = text.replace(/&#39;/g,'"');
        text = text.replace(/&quot;/g,'"');
        var data = JSON.parse(text);
        if(data.total>0) {
            var html = ("<div><div class='cell'><div class='cell-overflow'>");
            html = html.concat("<table id='table2' ", getColors(), "><thead><tr><th>Vehicle ID</th><th>Address</th></tr></thead></table></div></div>");
            html = html.concat("<br/><table><tr><td>Selected ID:&nbsp;</td><td><input type='text' size='10' id='selected_id' readonly ", getColors(), "></td></tr>");
            html = html.concat("<tr><td>Start Date:&nbsp;</td><td><input type='text' size='10' readonly='true' value='", localStorage.getItem("tesla_startdate"), "' id='startdate'");
            html = html.concat(" onClick='pickDate($(this));' ", getColors(), "'>");
            html = html.concat("</td></tr><tr><td>End Date:</td><td><input type='text' size='10' value='", today(), "' readonly='true' id='enddate'");
            html = html.concat(" onClick='pickDate($(this));' ", getColors(), "'>");
            html = html.concat("</td></tr></table><br/><table width='100%'><tr><td width='50%'>");
            html = html.concat("Select Plot Variable:<br/>", radio(plotoptions_desc,plotoptions_opt,["tesla_plotoptions_desc", "tesla_plotoptions"]), "<br/>");
            html = html.concat("Range Filter for Curve Fit:<br/>", radio(filteroptions_desc,filteroptions_opt,["tesla_filteroptions_desc", "tesla_filteroptions"]), "<br/>");
            html = html.concat("Plot Type:<br/>", radio(plottype_desc,plottype_opt,["tesla_plottype_desc", "tesla_plottype"]), "<br/>");
            html = html.concat("</form><button onclick='plotData();' class='btn btn-secondary'>Show Plot</button>");
            html = html.concat("</td><td width='50%'>");
            html = html.concat("Show Range As:&nbsp;&nbsp;&nbsp;<br/>", radio(range_desc,range_opt,["tesla_range_desc","tesla_range"]), "<br/>");
            html = html.concat("Show Temperature As:&nbsp;&nbsp;&nbsp;<br/>", radio(temperature_desc,temperature_opt,["tesla_temperature_desc","tesla_temperature"]), "<br/>");
            html = html.concat("Select Table Variable:");
            html = html.concat("<br/>", radio(tablevar_desc,tablevar_opt,["tesla_tablevar_desc", "tesla_tablevar"]), "<br/>");
            html = html.concat("PDF Format:<br/>", radio(PDFOptions_desc,PDFOptions_opt,["tesla_PDFOptions_desc", "tesla_PDFOptions"]), "<br/>");
            html = html.concat("PDF Image File (stored in wallet/crystals/420_tesla/static): <input type='text' value='",localStorage.getItem("tesla_pdfimage"), "' id='pdf_image' class='form-control'", getColors(), ">");
            html = html.concat("</form><button onclick='showTable();' class='btn btn-secondary'>Show Table</button>");
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
                if(localStorage.getItem("tesla_selected_id").length>0) {
                    $('#selected_id').val(localStorage.getItem("tesla_selected_id"));
                }
            } catch(e) {}
            $('#table2 tbody').on('click', 'tr', function () { $('#selected_id').val(table.row(this).data()); localStorage.setItem('tesla_selected_id',$('#selected_id').val()); });
            $(".content").css({"cursor":"default"});
        }
    });
}

function plotData() {
    //Fetches vehicle data for a given VIN and displays ChartJS plot on Page3
    var xsrf = $("[name='_xsrf']").val();
    var variable = getLocal("tesla_plotoptions",plotoptions_opt[0]);
    var variable_desc = getLocal("tesla_plotoptions_desc",plotoptions_desc[0]);
    var rangeval = getLocal("tesla_range",range_opt[0]);
    var temperature = getLocal("tesla_temperature",temperature_opt[0]);
    var plottype = getLocal("tesla_plottype",plottype_opt[0]);
    var plot_desc = getLocal("tesla_plottype_desc",plottype_desc[0]);
    var f = getLocal("tesla_filteroptions",filteroptions_opt[0]);
    var d0 = $("#startdate").val();
    var d1 = $("#enddate").val();
    var selected_id = $("#selected_id").val().split(",");
    var asset_id = selected_id[0];
    var address = selected_id[1];

    if(variable_desc.indexOf("Temperature")>=0) {
        variable_desc = variable_desc + " (deg " + getLocal("tesla_temperature",temperature_opt[0]) + ")";
    } else if((variable_desc.indexOf("Odometer")>=0) || (variable_desc.indexOf("Range")>=0)) {
        variable_desc = variable_desc + " (" + getLocal("tesla_range",range_opt[0]) + ")";
    }

    updateLocalStorage();

    $.post('get_chain_data', { vin: asset_id, address: address, variable: variable, filter: f, range: rangeval, temperature: temperature, startdate: d0, enddate: d1, _xsrf: xsrf }, function(text){
        text = text.replace(/&#39;/g,'"');
        text = text.replace(/&quot;/g,'"');
        var data = JSON.parse(text);
        var x = new Array();
        var y = new Array();
        var xy = new Array();
        for(i=0; i<data.x.length; i++) {
            x.push(data.x[i]);
            y.push(data.y[i]);
            xy.push({"x": range2(data.x[i]), "y": data.y[i]});
        }
        $('#myChart').remove();
        $('#div_plot').append('<canvas id="myChart"><canvas>');
        var ctx = $('#myChart').get(0).getContext('2d');
        var col = "rgba(77,166,83,1.0)";
        var fill = false;
        if(plot_desc.indexOf("Fill") >= 0) { fill = true; }
        if(variable == "battery_cycles") {
            plottype = "bar";
        }

        if(variable.search("_vs_odometer")>0) {
            var z_x = new Array();
            var z_y = new Array();
            var xz = new Array();
            for(i=0; i<data.z_x.length; i++) {
                z_x.push(data.z_x[i]);
                z_y.push(data.z_y[i]);
                xz.push({"x": range2(data.z_x[i]), "y": data.z_y[i]});
            }
            var options = { "scales": { "xAxes": [{ "type": "linear", "ticks": { "autoSkip": true, "maxRotation": 90, "minRotation": 90 } }], "yAxes":[{"type":"linear","id":"y1","display":"true","position":"left"}] } }
            var chart = new Chart(ctx,{"data":{"datasets":[{"type":"scatter", "label": variable_desc, "backgroundColor":col,"data": xy,"fill":fill, "pointRadius": 5, "borderColor":"green","yAxisID":"y1"},{"type":"line","label": "Curve Fit","backgroundColor":col,"data": xz,"fill":fill, "pointRadius": 1, "borderColor":"red","yAxisID":"y1"}]},"options": options});
        } else {
            var options = { "scales": { "xAxes": [{ "ticks": { "autoSkip": true, "maxRotation": 90, "minRotation": 90 } }] } }
            var chart = new Chart(ctx,{"type":plottype,"data":{"labels": x ,"datasets":[{"label":variable_desc,"backgroundColor":col,"data": y,"fill":fill, "pointRadius": 4, "borderColor":"gray"}]},"options": options});
        }
    });
};
