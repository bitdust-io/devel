<!-- autogame footer -->
<script>
    $(document).ready(function() {
        $('.game_status').click(function() {
            $("body").css("cursor", "progress");
            hash = $(this).attr('data-hash');
            /* We could get and process the json in JS, but I prefer to handle the max in python code for constitency */
            $.get('/crystal/autogame/status_pop?hash='+hash,function(page){
                $("#detail").html(page);
                $("body").css("cursor", "default");
            });
        });
        $('.game_replay').click(function() {
            hash = $(this).attr('data-hash');
            $("body").css("cursor", "progress");
            /* We could get and process the json in JS, but I prefer to handle the max in python code for constitency */
            $.get('/crystal/autogame/replay_pop?hash='+hash,function(page){
                $("#detail").html(page);
                $("body").css("cursor", "default");
            });
        });

        $('#reg_bisurl').click(function() {
            sendurl($('#bisurl').val());
        });



    });

</script>
