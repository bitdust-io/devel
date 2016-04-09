
tpl_status = "{.section status}{@}{.end}"
tpl_result = "{.section result}{.repeated section @}{@}\n{.end}{.end}"
tpl_errors = "{.section errors}{.repeated section @}{@}\n{.end}{.end}"
tpl_execution = "{.section execution}: {@} sec.{.end}"

TPL_RAW = """{0}{1}
{2}{3}
""".format(tpl_status, tpl_execution, tpl_result, tpl_errors)

#------------------------------------------------------------------------------ 

tpl_backups = "{.section result}{.repeated section @}{id} {type} {size} {path} {.section versions}{.repeated section @}[{version}: {size} (#{blocks})]{.end}{.end}\n{.end}{.end}"

TPL_BACKUPS_LIST = """{0}{1}
{2}{3}
""".format(tpl_status, tpl_execution, tpl_backups, tpl_errors)

#------------------------------------------------------------------------------ 

tpl_backups_ids = "{.section result}{.repeated section @}{backupid} {size} {path}\n{.end}{.end}"

TPL_BACKUPS_LIST_IDS = """{0}{1}
{2}{3}
""".format(tpl_status, tpl_execution, tpl_backups_ids, tpl_errors)

#------------------------------------------------------------------------------ 

tpl_options = "{.section result}{.repeated section @}{key} ({type}) : {value}\n{.end}{.end}"

TPL_OPTIONS_LIST_KEY_TYPE_VALUE = """{0}{1}
{2}{3}
""".format(tpl_status, tpl_execution, tpl_options, tpl_errors)

#------------------------------------------------------------------------------ 

tpl_option = "{.section result}{.repeated section @}{key} ({type}) : {value}{.section old_value}, previous : {@}{.or}{.end}\n{.end}{.end}"

TPL_OPTION_MODIFIED = """{0}{1}
{2}{3}
""".format(tpl_status, tpl_execution, tpl_option, tpl_errors)

TPL_OPTION_SINGLE = """{0}{1}
{2}{3}
""".format(tpl_status, tpl_execution, tpl_option, tpl_errors)

#------------------------------------------------------------------------------ 

TPL_FRIEND_LOOKUP = """{.section result}
friend lookup:
    {result}
    {nickname}
    {position}
    {idurl}
{.end}"""


TPL_FRIEND_LOOKUP_REPEATED_SECTION = """{.section result}
friends:
{.repeated section @}
    {idurl} : {nickname}
{.end}
{.end}"""


TPL_MESSAGE_SENDING = """{.section result}
    {@}
{.end}
{.section error}
    error: {@}
{.end}
    recipient: {.section recipient}{@}{.end}
"""

