<!-- script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.7.2/Chart.min.js"></script -->
<script src="/static/js/plugins/Chart.min.js"></script>

<script>
    $(function() {
        var abil = {% raw abilities %};
        var ctxR = document.getElementById("radar").getContext('2d');
        var myRadarChart = new Chart(ctxR, {
            type: 'radar',
            data: {
                labels: ['{{_("strategy")}}','{{_("bravery")}}', '{{_("strength")}}', '{{_("agility")}}', '{{_("power")}}', '{{_("stamina")}}', '{{_("speed")}}', '{{_("health")}}'],
                datasets: [{
                    label: "",
                    backgroundColor: "rgba(104, 223, 240,0.5)",
                    borderColor: "#68dff0",
                    fillColor: "rgba(220,255,220,1)",
                    strokeColor: "rgba(220,255,220,1)",
                    pointColor: "rgba(220,255,220,1)",
                    pointStrokeColor: "#fff",
                    pointHighlightFill: "#afa",
                    pointHighlightStroke: "rgba(220,220,220,1)",
                    data: abil[0]
                }]
            },
            options: {
                responsive: true,
                legend: {
                    display: false
                },
                scale: {
                    ticks: {
                        min: 0,
                        max: 100
                    }

                }
            }
        });
    });
</script>



<script>
$(".tab-selector").click(function(){

$(".tab-selector").removeClass("active");
$( this ).addClass("active");
});
</script>
