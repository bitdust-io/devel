$(document).ready(function() {
    try {
        display_mode(localStorage.getItem("phone_mode"));
    } catch(e) {}
    try { //Page2
        if($("#phone_pwd").val() === "") {
            $("#phone_pwd").val(localStorage.getItem("phone_pwd"));
        }
    } catch(e) {}
    try { //Page3
        if(localStorage.getItem("phone_startdate") === null) {
            localStorage.setItem("phone_startdate", "2020-01-01");
            localStorage.setItem("phone_enddate", today());
            localStorage.setItem("phone_pdfimage", "pdflogo.png");
        }
    } catch(e) {}
});
