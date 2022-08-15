<!-- script src="https://cdn.datatables.net/1.10.19/js/jquery.dataTables.min.js"></script -->
<script src="/static/js/plugins/jquery.dataTables.min.js"></script>

<script>
$(document).ready(function() {
    $('#egg_list').DataTable({ {% raw bismuth['dtlanguage'] %} });
});
</script>
