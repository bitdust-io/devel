from decimal import Decimal
import regnet
import math
import time
from fork import Fork
from quantizer import quantize_two, quantize_ten


_Debug = False

DEFAULT_DIFFICULTY = 10


def difficulty(node, db_handler):

    difficulty = [DEFAULT_DIFFICULTY, DEFAULT_DIFFICULTY, 0, 0, 0, 0, 0, 0]
    return difficulty

    try:
        fork = Fork()

        db_handler.execute(db_handler.c, 'SELECT * FROM transactions WHERE reward != 0 ORDER BY block_height DESC LIMIT 2')
        result = db_handler.c.fetchone()

        timestamp_last = Decimal(result[1])
        block_height = int(result[0])

        node.last_block_timestamp = timestamp_last
        #node.last_block = block_height do not fetch this here, could interfere with block saving

        previous = db_handler.c.fetchone()

        node.last_block_ago = int(time.time() - int(timestamp_last))

        # Failsafe for regtest starting at block 1}
        timestamp_before_last = timestamp_last if previous is None else Decimal(previous[1])

        db_handler.execute_param(db_handler.c, ('SELECT timestamp FROM transactions WHERE block_height > ? AND reward != 0 ORDER BY block_height ASC LIMIT 2'), (block_height - 1441, ))
        timestamp_1441 = Decimal(db_handler.c.fetchone()[0])
        block_time_prev = (timestamp_before_last - timestamp_1441)/1440
        temp = db_handler.c.fetchone()
        timestamp_1440 = timestamp_1441 if temp is None else Decimal(temp[0])
        block_time = Decimal(timestamp_last - timestamp_1440)/1440

        db_handler.execute(db_handler.c, 'SELECT difficulty FROM misc ORDER BY block_height DESC LIMIT 1')
        diff_block_previous = Decimal(db_handler.c.fetchone()[0])

        time_to_generate = timestamp_last - timestamp_before_last

        if node.is_regnet:
            return (float('%.10f' % regnet.REGNET_DIFF), float('%.10f' % (regnet.REGNET_DIFF - 8)), float(time_to_generate), float(regnet.REGNET_DIFF), float(block_time), float(0), float(0), block_height)

        try:
            hashrate = pow(2, diff_block_previous/Decimal(2.0))/(block_time*math.ceil(28 - diff_block_previous/Decimal(16.0)))
            # Calculate new difficulty for desired blocktime of 60 seconds
            target = Decimal(60.00)
            ##D0 = diff_block_previous
            difficulty_new = Decimal((2/math.log(2))*math.log(hashrate*target*math.ceil(28 - diff_block_previous/Decimal(16.0))))
        except:
            hashrate = 1
            difficulty_new = 10

        # Feedback controller
        Kd = 10
        difficulty_new = difficulty_new - Kd*(block_time - block_time_prev)
        diff_adjustment = (difficulty_new - diff_block_previous)/720  # reduce by factor of 720

        if diff_adjustment > Decimal(1.0):
            diff_adjustment = Decimal(1.0)

        difficulty_new_adjusted = quantize_ten(diff_block_previous + diff_adjustment)
        difficulty = difficulty_new_adjusted

        #fork handling
        # if node.is_mainnet:
        #     if block_height == fork.POW_FORK - fork.FORK_AHEAD:
        #         fork.limit_version(node)
        #fork handling

        diff_drop_time = Decimal(180)

        if Decimal(time.time()) > Decimal(timestamp_last) + Decimal(2*diff_drop_time):
            # Emergency diff drop
            time_difference = quantize_two(time.time()) - quantize_two(timestamp_last)
            diff_dropped = quantize_ten(difficulty) - quantize_ten(1) \
                           - quantize_ten(10 * (time_difference - 2 * diff_drop_time) / diff_drop_time)
        elif Decimal(time.time()) > Decimal(timestamp_last) + Decimal(diff_drop_time):
            time_difference = quantize_two(time.time()) - quantize_two(timestamp_last)
            diff_dropped = quantize_ten(difficulty) + quantize_ten(1) - quantize_ten(time_difference/diff_drop_time)
        else:
            diff_dropped = difficulty

        if difficulty < 50:
            difficulty = 50
        if diff_dropped < 50:
            diff_dropped = 50

        # TODO: Verify!
        difficulty = DEFAULT_DIFFICULTY
        diff_dropped = DEFAULT_DIFFICULTY

        return (
            float('%.10f' % difficulty),
            float('%.10f' % diff_dropped),
            float(time_to_generate),
            float(diff_block_previous),
            float(block_time),
            float(hashrate),
            float(diff_adjustment),
            block_height,
        )  # need to keep float here for database inserts support
    except Exception as e:  #new chain or regnet
        if _Debug:
            print('Failed to calculate difficulty (default difficulty will be used):', e)
        # import traceback
        # traceback.print_exc()
        difficulty = [DEFAULT_DIFFICULTY, DEFAULT_DIFFICULTY, 0, 0, 0, 0, 0, 0]
        return difficulty
