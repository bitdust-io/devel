##### Install Bismuth requirements

        cd bitdust/blockchain/
	~/.bitdust/venv/bin/python -m pip install -r requirements.txt



##### First make sure you have a backup of the existing Ledger data files and then erase them:

        cd bitdust/blockchain/Bismuth/
        cp -v address.txt config.txt *.db privkey.der pubkey.der static/*.db ../genesis1/
        rm -rf address.txt config.txt *.db privkey.der pubkey.der static/*.db



##### Generate first genesis block (Must be executed one time on the first seeding node):

        ~/.bitdust/venv/bin/python genesis.py >genesis.log
        cp genesis.log ../genesisN



##### Backup generated files to genesis1/ folder:

        cp -v address.txt mempool.db privkey.der pubkey.der static/*.db ../genesis1



##### Check out the genesis block and manually update node.py and options.py

Open `ledger.db` and `hyper.db` files in `sqlitebrowser` and copy-paste field values of the first block. You can also use command line `sqlite3` tool:

You will have to manually update the `node.py` and `options.py` files:

        sqlite3 static/ledger.db "select * from transactions;"
        sqlite3 static/hyper.db "select * from transactions;"
        # open node.py and update code inside bootstrap() method : look for "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)" line
        # open options.py and update genesis address on line 112
        # open modules/config.py and update genesis address on line 74



##### Erase generated files:

        rm -rfv address.txt mempool.db privkey.der pubkey.der static/*.db



##### Start the Bismuth Node:

        cp confilg.example.txt config.txt
        ~/.bitdust/venv/bin/python node.py



##### Start Bismuth Wallet Server in another terminal:

        cd bitdust/blockchain/Bismuth/
        cp wallet_server.example.txt wallet_server.txt
        ~/.bitdust/venv/bin/python wallet_server.py --verbose


##### Start Bismuth Wallet in another terminal:

        cd bitdust/blockchain/Bismuth/
        ~/.bitdust/venv/bin/python3 wallet/wallet.py --debug --verbose --server="127.0.0.1:8150"
        # Verify new file created : ~/.bismuth-private/wallet.json


##### Create new address for the miner:

Now open the wallet! Go to: http://localhost:8888

You should see a Web-based Crypto Wallet. Click "Dashboard" -> "addresses" (on the right) and then click "Create a new address" orange button.

Now you have two Bismuth addresses and you can use them to mine coins. One of them will be attached to the Mining pool and the second one we will use for the Miner to receive rewards.



##### Start the Mining Pool server in another terminal:

        cd bitdust/blockchain/Bismuth/
        cp pool.example.txt pool.txt
        # update pool.txt with first address from your Web-based Crypto Wallet
        ~/.bitdust/venv/bin/python optipoolware.py



##### Finally start the miner in another terminal and mine first coin:

	cd bitdust/blockchain/Bismuth/
	cp miner.example.txt miner.txt
        # update miner.txt with the second address from your Web-based Crypto Wallet
        ~/.bitdust/venv/bin/python optihash.py 1
