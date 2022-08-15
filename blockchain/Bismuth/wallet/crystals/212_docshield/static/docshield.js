var table = $('#missionTable').DataTable();

function update_table_deprecated(address) {
    // Ledger query
    url = 'http://127.0.0.1:8888/json/addlist/' + address;
    // TODO: maybe a stricter query could be use, to avoid huge data on busy addresses
    // Like get exact address + partial dochash:%
    response = JSON.parse(httpGet(url));
    table.clear();
    for(i=0; i<response.length-1; i++) {
        if (response[i][10].startsWith('dochash:')) {
            table.row.add([response[i][0], ts_to_ymdhms(response[i][1]),response[i][10],response[i][11]]).draw();
        }
    }
}

function add_from_url(url) {
    response = JSON.parse(httpGet(url));
    for(i=0; i<response.length; i++) {
        table.row.add([response[i][0], ts_to_ymdhms(response[i][1]),response[i][10],response[i][11]]).draw();
    }
}

function update_table(address) {
    $(".content").css({"cursor":"wait"});
    table.clear();
    add_from_url('http://127.0.0.1:8888/json/addlistopfrom/' + address + '/dochash:json')
    add_from_url('http://127.0.0.1:8888/json/addlistopfrom/' + address + '/dochash:sha256')
    $(".content").css({"cursor":"default"});
}


function check_exactopdata(op, data, field) {
    // Lookup for an exact match on operation and data fields.
    // Uses the integrated json gateway from the tornado wallet.
    url = 'http://127.0.0.1:8888/json/listexactopdatajson/' + op + '/' + data;
    // TODO: one drawback of having the host hardcoded is that the crystal will only work on a local setup. tornado wallet could also be used on a local network f.i.
    response = JSON.parse(httpGet(url));
    if(response.length>0) {
        status = 'Yes';
    } else {
        status = 'No';
    }
    if(field) {
        field.val(status);
    }
    return status;
}

function fileDialog() {
    $('#ip-file-input').trigger('click');
}

function loadFile(address) {
    if(address.length == 56) {
        input = document.getElementById('ip-file-input');
        file = input.files[0];
        $('#ip-file-size').val(file.size.toString());
        $('#ip-file-name').val(file.name);

        var reader = new FileReader();
        reader.onloadend = function(evt) {
            if (evt.target.readyState == FileReader.DONE) { // DONE == 2
                var hexdigest = CryptoJS.SHA256(CryptoJS.enc.Latin1.parse(evt.target.result)).toString(CryptoJS.enc.Hex)
                $('#ip-file-hash').val(hexdigest);

                $('#ip-recipient').val(address);
                // Transaction 1
                $('#ip-operation-1').val('dochash:sha256');
                datafield1 = hexdigest;
                $('#ip-datafield-1').val(datafield1);
                $('#ip-fee-1').html(0.01 + 1e-5*datafield1.length);
                // Transaction 2
                $('#ip-operation-2').val('dochash:json');
                datafield2 = '{"filename":"' + file.name + '", "size":' + file.size + ', "hash_type":"sha256", "hash":"' + hexdigest + '"}';
                $('#ip-datafield-2').val(datafield2);
                $('#ip-fee-2').html(0.01 + 1e-5*datafield2.length);

                check_exactopdata('dochash:sha256',datafield1,$('#ip-file-ledger-1'));
                check_exactopdata('dochash:json',datafield2,$('#ip-file-ledger-2'));

                update_table(address);
            }
        }
        var blob = file.slice(0, file.size);
        reader.readAsBinaryString(blob);
    } else {
        alert("First select a wallet address.");
    }
}

function ipSubmit(tx,balance) {
    address = $('#ip-recipient').val();

    if(tx == 1) {
        fee = parseFloat($('#ip-fee-1').text());
        operation = $('#ip-operation-1').val();
        datafield = $('#ip-datafield-1').val();
    } else {
        fee = parseFloat($('#ip-fee-2').text());
        operation = $('#ip-operation-2').val();
        datafield = $('#ip-datafield-2').val();
    }

    if(address.length == 56) {
        if(balance>=fee) {
            status = check_exactopdata(operation,datafield,'');
            if(status == "No") {
                send(address, 0, operation, datafield);
            } else {
                alert('Data already exists in ledger.');
            }
        } else {
            alert("Insufficient account balance.");
        }
    } else {
        alert("Not a valid recipient address.");
    }
}

$(function() {
    update_table(address)
});

