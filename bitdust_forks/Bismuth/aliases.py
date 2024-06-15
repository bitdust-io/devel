import log
import re


def replace_regex(string, replace):
    replaced_string = re.sub(r'^{}'.format(replace), '', string)
    return replaced_string


def aliases_update(node, db_handler_instance):
    db_handler_instance.index_cursor.execute('SELECT block_height FROM aliases ORDER BY block_height DESC LIMIT 1;')
    try:
        alias_last_block = int(db_handler_instance.index_cursor.fetchone()[0])
    except:
        alias_last_block = 0

    node.logger.app_log.warning('Alias anchor block: {}'.format(alias_last_block))

    db_handler_instance.h.execute('SELECT block_height, address, openfield FROM transactions WHERE openfield LIKE ? AND block_height >= ? ORDER BY block_height ASC, timestamp ASC;', ('alias=' + '%', ) + (alias_last_block, ))
    # include the anchor block in case indexation stopped there
    result = db_handler_instance.h.fetchall()

    for openfield in result:
        alias = (replace_regex(openfield[2], 'alias='))
        node.logger.app_log.warning(f'Processing alias registration: {alias}')
        try:
            db_handler_instance.index_cursor.execute('SELECT * from aliases WHERE alias = ?', (alias, ))
            dummy = db_handler_instance.index_cursor.fetchall()[0]  # check for uniqueness
            node.logger.app_log.warning(f'Alias already registered: {alias}')
        except:
            db_handler_instance.index_cursor.execute('INSERT INTO aliases VALUES (?,?,?)', (openfield[0], openfield[1], alias))
            db_handler_instance.index.commit()
            node.logger.app_log.warning(f'Added alias to the database: {alias} from block {openfield[0]}')


if __name__ == '__main__':
    app_log = log.log('aliases.log', 'WARNING', True)
