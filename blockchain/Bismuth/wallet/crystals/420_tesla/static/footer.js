$(document).ready(function() {
    try {
        display_mode(localStorage.getItem("tesla_mode"));
    } catch(e) {}
    try { //Page1 and 2
        if($("#tesla_pwd").val() === "") {
            $("#tesla_pwd").val(localStorage.getItem("tesla_pwd"));
        }
    } catch(e) {}
    try { //Page2
        if($("#tesla_email").val() === "") {
            $("#tesla_email").val(localStorage.getItem("tesla_email"));
            a = localStorage.getItem("tesla_range");
            $("#range option:contains(", a, ")").attr('selected', 'selected');
            a = localStorage.getItem("tesla_temperature");
            $("#temperature option:contains(", a, ")").attr('selected', 'selected');
        }
    } catch(e) {}
    try { //Page3
        if(localStorage.getItem("tesla_startdate") === null) {
            localStorage.setItem("tesla_startdate", "2020-01-01");
            localStorage.setItem("tesla_enddate", today());
            localStorage.setItem("tesla_pdfimage", "pdflogo.png");
        }
    } catch(e) {}
});
