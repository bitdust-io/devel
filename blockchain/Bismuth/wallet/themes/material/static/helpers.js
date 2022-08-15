// Helpers functions, factorize code

function float_to_bis(x){
  // Converts a float to a string, 8 decimals.
  return x.toFixed(8).replace(/\.?0*$/,'');
}

function httpGet(theUrl)
{
    // fetch an url and returns its content, synchronous
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.open( "GET", theUrl, false ); // false for synchronous request
    xmlHttp.send( null );
    return xmlHttp.responseText;
}

function ts_to_ymdhms(UNIX_timestamp){
  // converts a unix timestamp to a short human readble date/hour
  var a = new Date(UNIX_timestamp * 1000);
  var months = ['01','02','03','04','05','06','07','08','09','10','11','12'];
  var year = a.getFullYear();
  var month = months[a.getMonth()];
  var date = a.getDate();
  var hour = a.getHours();
  var min = a.getMinutes();
  var sec = a.getSeconds();
  var time = year + '-' + month + '-' + date + ':' + hour + ':' + min + ':' + sec ;
  return time;
}
