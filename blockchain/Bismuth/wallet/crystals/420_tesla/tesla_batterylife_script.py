# This script demonstrates how to send Tesla battery data without
# using the TornadoWallet interface. If you are submitting data
# on a regukar basis, after a while it may feel time consuming to
# start the wallet, select the address, activate the crystal, fetch
# the data, and submit, especially if data is submitted using Termux
# and you are not at home, or at a public supercharger.
# This script does the steps for you which previously required the
# TornadoWallet. The script also demonstrates how to use a
# multi-wallet together with bismuthclient in a script.
# Note: the script assumes that the wallet is not encrypted.
#
# This script could also form the basis for an IOT (internet-of-
# things) script for Bismuth. The user input could for example
# be replaced and the script placed in a regular cron job.

import json
from bismuthclient.bismuthclient import BismuthClient
from teslaapihandler import TeslaAPIHandler

if __name__ == "__main__":
    client = BismuthClient() #Empty server list to use api
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
        email = input("Enter your Tesla email address: ")
        pwd = input("Enter your vehicle anonymizer password (not your Tesla account password): ")

        tesla = TeslaAPIHandler("", "", "", "")
        out = tesla.fetch_vehicle_data(email, pwd)
        operation = "tesla:battery"
        recipient = "Bis1TeSLaWhTC2ByEwZnYWtsPVK5428uqnL46"
        data = json.dumps(out)
        print(data)
        user_input = input("Submit this data (y/n) ? ")
        if user_input == "y":
            client.send(recipient=recipient, amount=1.0, operation=operation, data=data)
            print("Sent")
    else:
        print("Input error")
