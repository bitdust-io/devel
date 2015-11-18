

TPL_RAW = """{.section result}
    {@}
{.end}"""


TPL_BACKUPS_LIST = """{.section result}
{.repeated section @}
    {id} {type} {size} {path} {.section versions}{.repeated section @}[{version}: {size} (#{blocks})]{.end}{.end} 
{.end}
{.end}"""


TPL_BACKUPS_LIST_IDS = """{.section result}
{.repeated section @}
    {backupid} {size} {path}
{.end}
{.end}"""


TPL_OPTIONS_LIST_KEY_TYPE_VALUE = """{.section result}
{.repeated section @}
    {key} ({type}) : {value}
{.end}
{.end}"""


TPL_OPTION_MODIFIED_WITH_ERROR = """{.section result}
{.section error}
    {@}
{.or}
    {key} ({type}) : {value}
{.section old_value}
    previous value : {@}
{.or}
{.end}    
{.end}
{.end}"""


TPL_OPTION_MODIFIED = """{.section result}
    {key} ({type}) : {value}
{.section old_value}
    previous value : {@}
{.or}
{.end}
{.end}"""


TPL_OPTION_SINGLE = """{.section result}
{.section error}
    {@}
{.or}
    {key} ({type}) : {value}
{.end}
{.end}"""


TPL_FRIEND_LOOKUP = """{.section result}
    {result}
    {nickname}
    {position}
    {idurl}
{.end}"""


TPL_FRIEND_LOOKUP_REPEATED_SECTION = """{.section result}
{.repeated section @}
    {idurl} : {nickname}
{.end}
{.end}"""




