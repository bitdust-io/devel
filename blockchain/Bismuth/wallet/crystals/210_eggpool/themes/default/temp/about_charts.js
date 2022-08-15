
<!-- script src="/static/js/plugins/chartist-plugin-legend.js"></script -->
<!-- script>
$(document).ready(function() {

    if ($('#sharesViewsChart').length != 0) {

      dataSharesViewsChart = {
        labels: ['-12', '-11', '-10', '-9', '-8', '-7', '-6', '-5', '-4', '-3', '-2', '-1', '0'],
        series: [
          {%raw shares_series %}
          /*[12, 17, 7, 17, 23, 18, 38]*/
        ]
      };

      optionsSharesViewsChart = {
        lineSmooth: Chartist.Interpolation.cardinal({
          tension: 0
        }),
        low: 0,
        //high: 50, // we recommend you to set the high sa the biggest value + something for a better look
        chartPadding: {
          top: 0,
          right: 0,
          bottom: 0,
          left: 0
        },
        plugins: [
        Chartist.plugins.legend({
            legendNames: {% raw workers_name %},
        })
      ]
      }

      var sharesViewsChart = new Chartist.Line('#sharesViewsChart', dataSharesViewsChart, optionsSharesViewsChart);
    }
});

</script -->
