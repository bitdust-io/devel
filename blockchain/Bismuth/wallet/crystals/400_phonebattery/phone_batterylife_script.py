# This script demonstrates how to send battery data from your phone
# without using the TornadoWallet interface. If you are submitting
# data from your phone on a daily basis, after a while it may feel
# time consuming on Termux to start the wallet, select the address,
# activate the crystal, fetch the data, and submit. This script
# does these steps for you. The script also demonstrates how
# to use a multi-wallet together with bismuthclient. Note: the script
# assumes that the wallet is not encrypted.
#
# This script could also form the basis for an IOT (internet-of-
# things) script for Bismuth. The user input could for example
# be replaced and the script placed in a regular cron job.

import json
from bismuthclient.bismuthclient import BismuthClient
from phoneapihandler import PhoneAPIHandler

if __name__ == "__main__":
    client = BismuthClient(servers_list={'wallet2.bismuth.online:5658'})
    client.load_multi_wallet("../../../../bismuth-private/wallet.json")
    n = len(client._wallet._addresses)
    print("Available addresses in multi-wallet:")
    for i in range(n):
        print("{}. {}".format(i+1,client._wallet._addresses[i]['address']))
    user_input = input("Select an address (1-{}): ".format(n))
    try:
        val = int(user_input)
    except ValueError:
        print("Input error")
        raise

    if val>0 and val<=n:
        address = client._wallet._addresses[val-1]['address']
        client.set_address(address)
        print("Selected address = ", client.address)
        pwd = input("Enter your anonymizer password: ")

        phone = PhoneAPIHandler("", "", "", "")
        out = phone.fetch_asset_data(pwd)
        operation = "phone:battery"
        recipient = "Bis1QPHone8oYrrDRjAFW1sNjyJjUqHgZhgAw"
        data = json.dumps(out)
        print(data)
        user_input = input("Submit this data (y/n) ? ")
        if user_input == "y":
            client.send(recipient=recipient, amount=1.0, operation=operation, data=data)
            print("Sent")
    else:
        print("Input error")
