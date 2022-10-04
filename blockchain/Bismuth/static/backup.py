import time
from shutil import copyfile

interval = 43200

while True:
    copyfile("ledger.db", "C:\\Users\\Meegopad\\Google Drive\\ledger\\ledger.db")
    print(
        "Backup complete at {}, interval of {} minutes ({} hours)".format(
            time.strftime("%Y/%m/%d,%H:%M:%S", time.gmtime()),
            interval / 60,
            interval / 60 / 60,
        )
    )
    time.sleep(interval)
