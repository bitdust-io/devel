<script src="/static/js/plugins/Chart.min.js"></script>

<script>
$(document).ready(function() {


    var lineChartDataSH = {
        labels: ['H-12', 'H-11', 'H-10', 'H-9', 'H-8', 'H-7', 'H-6', 'H-5', 'H-4', 'H-3', 'H-2', 'H-1', 'H'],
        datasets: {% raw sh_datasets %}
    }

    var lineChartDataHR = {
        labels: ['H-12', 'H-11', 'H-10', 'H-9', 'H-8', 'H-7', 'H-6', 'H-5', 'H-4', 'H-3', 'H-2', 'H-1', 'H'],
        datasets: {% raw hr_datasets %}
    }

        var lineChartOptions = {
            //Boolean - If we should show the scale at all
            showScale: true,
            //Boolean - Whether grid lines are shown across the chart
            scaleShowGridLines: true,
            //String - Colour of the grid lines
            scaleGridLineColor: 'rgba(100,100,100,.05)',
            //Number - Width of the grid lines
            scaleGridLineWidth: 1,
            //Boolean - Whether to show horizontal lines (except X axis)
            scaleShowHorizontalLines: true,
            //Boolean - Whether to show vertical lines (except Y axis)
            scaleShowVerticalLines: true,
            //Boolean - Whether the line is curved between points
            bezierCurve: true,
            //Number - Tension of the bezier curve between points
            bezierCurveTension: 0.3,
            //Boolean - Whether to show a dot for each point
            pointDot: false,
            //Number - Radius of each point dot in pixels
            pointDotRadius: 4,
            //Number - Pixel width of point dot stroke
            pointDotStrokeWidth: 1,
            //Number - amount extra to add to the radius to cater for hit detection outside the drawn point
            pointHitDetectionRadius: 20,
            //Boolean - Whether to show a stroke for datasets
            datasetStroke: true,
            //Number - Pixel width of dataset stroke
            datasetStrokeWidth: 2,
            //Boolean - Whether to fill the dataset with a color
            datasetFill: false,
            //String - A legend template
            //Boolean - whether to maintain the starting aspect ratio or not when responsive, if set to false, will take up entire container
            maintainAspectRatio: true,
            //Boolean - whether to make the chart responsive to window resizing
            responsive: true,
            scales: {
            yAxes: [{
                ticks: {
                    beginAtZero:true
                }
            }]
        }
        }

        //-------------
        //- LINE CHART -
        //--------------
        var lineChartCanvas = $('#lineChartHR').get(0).getContext('2d')
        //var lineChart = new Chart(lineChartCanvas)
        /* var lineChartOptions = lineChartOptions
        lineChart.line(lineChartDataHR, lineChartOptions) */
        var lineChart = new Chart(lineChartCanvas, {
            type: 'line',
            data: lineChartDataHR,
            options: lineChartOptions
        });

        var lineChartCanvas2 = $('#lineChartSH').get(0).getContext('2d')
        //var lineChart2 = new Chart(lineChartCanvas2)
        var lineChartOptions2 = lineChartOptions
        //lineChartOptions2.legendTemplate = false
        //lineChart2.line(lineChartDataSH, lineChartOptions2)
        var lineChart2 = new Chart(lineChartCanvas2, {
            type: 'line',
            data: lineChartDataSH,
            options: lineChartOptions2
        });


    });

</script>
