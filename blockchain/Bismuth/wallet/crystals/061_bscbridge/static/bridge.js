

const ethEnabled = () => {
    if (window.web3) {
        window.web3 = new Web3(window.ethereum);
        //const accounts = window.ethereum.request('eth_requestAccounts');
        web3.eth.requestAccounts(function(err, res) {
        account = res[0];
        web3.eth.defaultAccount = account;
        console.log("using account", account);
        });
        return true;
    }
    return false;
}

if (!ethEnabled()) {
    alert("Please install MetaMask to use this dApp!");
    console.log("Please install MetaMask to use this dApp!");
}


 function bisAddressToHex(str) {
    var result = '0x';
    if (str[1] == 'i') {
        for (var i=0; i<str.length; i++) {
            result += str.charCodeAt(i).toString(16);
        }
    } else {
        // Old style bis address
        result += str;
    }
    return result;
  }


// Creates an instance of the smart contract, passing it as a property,
// which allows web3.js to interact with it.
function Token(Contract) {
    this.web3 = null;
    this.instance = null;
    this.Contract = Contract;
}

// Initializes the `Token` object and creates an instance of the web3.js library,
Token.prototype.init = function () {
    // Creates a new Web3 instance using a provider
    // Learn more: https://web3js.readthedocs.io/en/v1.2.0/web3.html
    this.web3 = new Web3(
        window.ethereum ||
        new Web3.providers.HttpProvider(this.Contract.endpoint)
    );
    this.web3.eth.handleRevert = true
    // Creates the contract interface using the web3.js contract object
    // Learn more: https://web3js.readthedocs.io/en/v1.2.0/web3-eth-contract.html#new-contract
    var contract_interface = new this.web3.eth.Contract(this.Contract.abi,this.Contract.address);
    this.instance = contract_interface;
};

Token.prototype.showTotal = async function () {
    balance = await this.instance.methods.totalSupply().call();
    console.log("wBIS total:", balance / 1E8);
    $("#wbis_total").html(balance / 1E8);

};

// Displays the token balance of an address, triggered by the "Check balance" button
Token.prototype.showAddressBalance = async function (hash, cb) {
    var that = this;
    // Gets form input value
    var address = $("#user_eth_address").val();

    // Validates address using utility function
    if (!isValidEthAddress(address)) {
        console.log("Invalid address");
        return;
    }

    // Gets the value stored within the `balances` mapping of the contract
    await this.getBalance(address, function (error, balance) {
        if (error) {
            console.log(error);
            $("#wbis_amount").html(error.message);
        } else {
            //console.log(balance / 1E8);
            $("#wbis_amount").html(balance / 1E8);
        }
    });
};

// Returns the token balance (from the contract) of the given address
Token.prototype.getBalance = async function (address, cb) {
    try {
        balance = await this.instance.methods.balanceOf(address).call();
        error = null;
    } catch(e) {
        error = e;
        balance = 0;
    }
    cb(error, balance);
};

Token.prototype.burnTokens = async function () {
    $("#burn_result").html("");
    var that = this;
    // Gets form input values
    var address = $("#burn_recipient").val();
    var amount = $("#burn_amount").val();
    var gwei = $("#gwei").val();
    console.log("start burn:", address, amount);

    // Validates address using utility function
    if (!isValidBisAddress(address)) {
        console.log("Invalid BIS address.", address);
        $("#burn_result").html("Invalid BIS address");
        return;
    }

    if (!isValidAmount(amount)) {
        console.log("Invalid amount");
        $("#burn_result").html("Invalid amount");
        return;
    }
    if (amount < 0.001) {
        console.log("Invalid amount");
        $("#burn_result").html("Amount is too small, Min 10 wBIS because of fees.");
        return;
    }

    amount = parseInt(amount * 1E8);
    console.log("burn:", address, amount)

    // burn wbis
    $("#burn").attr('disabled','disabled');
    $("#burn_result").html('<i class="fas fa-2x fa-spinner fa-spin"></i> Please wait for the transaction to be confirmed');
    try{
        txHash = await this.instance.methods.burn(
            amount,
            bisAddressToHex(address)
        ).send({from: $("#user_eth_address").val(),
            gas: 100000,
            //gasPrice: 150000000000,
            gasPrice: gwei * 1000000000,
            gasLimit: 200000
            });
        console.log(txHash.transactionHash);
            $("#burn_result").html("<span class=\"label label-success\">tx:<a target=\"_blank\" href=\"https://bscscan.com/tx/"
                + txHash.transactionHash + "\">" + txHash.transactionHash + "</a></span>");
            $("#burn_txid").val(txHash.transactionHash);
            $("#burn").removeAttr('disabled');
            await this.showAddressBalance();
    } catch(error) {
        console.log(error);
        $("#burn_result").html("<span class=\"label label-success\">"+error.message+"</span>");
        $("#burn_txid").val("");
        $("#burn").removeAttr('disabled');
        return
    }

};


Token.prototype.signMint = async function () {
    //const accounts = window.ethereum.request('eth_requestAccounts');
    /*web3.eth.getAccounts(function(err,res) {
        accounts = res;
        account = accounts[0];
        console.log("using account", account);
    });*/
   console.log("Using", web3.eth.defaultAccount);
   // https://web3js.readthedocs.io/en/v1.2.0/web3-utils.html#sha3
   // https://web3js.readthedocs.io/en/v1.2.0/web3-utils.html#soliditysha3
    var address = $("#mint_recipient").val();
    var amount = $("#mint_amount").val();
    amount = parseInt(amount * 1E8);
    var txid = $("#mint_tx").val();

   encoded = await web3.utils.soliditySha3(
   {t: 'address' , v: address},
   {t: 'uint256', v: amount},
   {t: 'bytes32', v: txid}
   );
   console.log("encoded", encoded);

   //res = await web3.eth.personal.sign(encoded, web3.eth.defaultAccount, "");
   //console.log("sign", res);
   encoded2 = await web3.utils.soliditySha3(
   "\x19Ethereum Signed Message:\n32",
   {t: 'bytes32', v: encoded}
   );
   console.log("encoded2", encoded2);
   resb = await web3.eth.sign(encoded2, web3.eth.defaultAccount);
   console.log("signb", resb);
   res2 = await web3.eth.personal.ecRecover(encoded, resb)
   console.log("signer", res2);
   tx = await this.instance.methods.msgMint(
            address,
            amount,
            txid
        ).send({from: $("#user_eth_address").val(),
            gas: 100000,
            gasPrice: 150000000000,
            gasLimit: 200000
            });
   console.log("tx", tx);


}

Token.prototype.mintTokens = async function () {
    $("#mint_result").html("");
    var that = this;
    // Gets form input values
    var address = $("#mint_recipient").val();
    var amount = $("#mint_amount").val();
    var txid = $("#mint_tx").val();
    var auth = $("#mint_auth").val();
    var gwei = $("#gwei").val();
    console.log("start mint:", address, amount, txid, auth);

    // Validates address using utility function
    if (!isValidEthAddress(address)) {
        console.log("Invalid address.", address);
        $("#mint_result").html("Invalid ETH address");
        return;
    }

    if (!isValidAmount(amount)) {
        console.log("Invalid amount");
        $("#mint_result").html("Invalid amount");
        return;
    }
    if (amount < 5) {
        console.log("Invalid amount");
        $("#mint_result").html("Amount is too small, Min 5 BIS after fees.");
        return;
    }

    amount = parseInt(amount * 1E8);
    console.log("mint:", address, amount)

    // burn wbis
    $("#mint").attr('disabled','disabled');
    $("#mint_result").html('<i class="fas fa-2x fa-spinner fa-spin"></i> Please wait for the transaction to be confirmed');
    try{
        tx = await this.instance.methods.relayMint(
            address,
            amount,
            txid,
            auth
        ).send({from: $("#user_eth_address").val(),
            gas: 150000,
            //gasPrice: 150000000000,
            gasPrice: gwei * 1000000000,
            gasLimit: 150000
            });
        console.log(tx.transactionHash);
            $("#mint_result").html("<span class=\"label label-success\">tx:<a target=\"_blank\" href=\"https://bscscan.com/tx/"
                + tx.transactionHash + "\">" + tx.transactionHash + "</a></span>");
            $("#mint").removeAttr('disabled');
    } catch(error) {
        console.log(error);
        $("#mint_result").html("<span class=\"label label-success\">"+error.message+"</span>");
        $("#mint").removeAttr('disabled');
        return
    }

};


// Checks if it has the basic requirements of a BIS address
function isValidBisAddress(address) {
    if (/^[0-9a-f]{56}$/i.test(address)) {
        // Legacy addresses
        return true;
    }
    if (/^^Bis1[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{28,52}$/.test(address)) {
        // Bis1 addresses
        return true;
    }
    return false;
}

function isValidEthAddress(address) {
    return /^(0x)?[0-9a-f]{40}$/i.test(address);
}

// Basic validation of amount. Bigger than 0 and typeof number
function isValidAmount(amount) {
    return amount > 0 && typeof Number(amount) == "number";
}

Token.prototype.bindBurnButtons = function () {
    var that = this;

    $(document).on("click", "#burn", function () {
        that.burnTokens();
    });

    $(document).on("click", "#refresh_balance", function () {
        that.showAddressBalance();
    });
};

Token.prototype.bindMintButtons = function () {
    var that = this;
    $(document).on("click", "#mint", function () {
        that.mintTokens();
    });
    $(document).on("click", "#sign", function () {
        that.signMint();
    });
    $(document).on("click", "#refresh_balance", function () {
        that.showAddressBalance();
    });
};


Token.prototype.addMeta = async function () {
    try {

        window.web3.currentProvider.sendAsync({
            method: 'metamask_watchAsset',
            params: {
              "type":"ERC20",
              "options":{
                "address": token.Contract.address,
                "symbol": "wBIS",
                "decimals": 8,
                "image": token.Contract.image_url,
              },
            },
            id: Math.round(Math.random() * 100000),
          }, (err, added) => {
            console.log('provider returned', err, added)
            });
    } catch(e) {
        console.log(e)
    }
};


Token.prototype.bindAboutButtons = function () {
    var that = this;
    $(document).on("click", "#addmeta", function () {
        that.addMeta();
    });
};

Token.prototype.updateAccounts= function(accounts) {
     $("#user_eth_address").val(accounts[0]);
     this.showAddressBalance();
}

// Creates the instance of the `Token` object
Token.prototype.onBurnReady = async function () {
    this.init();
    //if (this.hasContractDeployed()) {
    //    this.updateDisplayContent();
    this.bindBurnButtons();
    chain_id = await window.web3.eth.getChainId();
    if (token.Contract.chain_id != chain_id) {
        alert("Your Metamask is on the wrong chain. Please switch to "+token.Contract.chain_name);
    }

    //    this.showTotal();
    window.web3.eth.getAccounts(
        async function(error, accounts){
            $("#user_eth_address").val(accounts[0]);
            await token.showAddressBalance();
        }
    );
};

// Creates the instance of the `Token` object
Token.prototype.onMintReady = async function () {
    this.init();
    //if (this.hasContractDeployed()) {
    //    this.updateDisplayContent();
    this.bindMintButtons();
    chain_id = await window.web3.eth.getChainId();
    if (token.Contract.chain_id != chain_id) {
        alert("Your Metamask is on the wrong chain. Please switch to "+token.Contract.chain_name);
    }

    window.web3.eth.getAccounts(
        async function(error, accounts){
            $("#user_eth_address").val(accounts[0]);
            await token.showAddressBalance();
        }
    );
    //    this.showTotal();
};

// Creates the instance of the `Token` object
Token.prototype.onAboutReady = async function () {
    this.init();
    this.bindAboutButtons();
    chain_id = await window.web3.eth.getChainId();
    if (token.Contract.chain_id != chain_id) {
        alert("Your Metamask is on the wrong chain. Please switch to "+token.Contract.chain_name);
    }
    //console.log(token)
    //alert(net_version)
    /*window.web3.eth.getAccounts(
        async function(error, accounts){
            $("#user_eth_address").val(accounts[0]);
            await token.showAddressBalance();
        }
    );*/
    //    this.showTotal();
      window.web3.eth.getAccounts(
        async function(error, accounts){
            $("#my_ethaddress").html(accounts[0]);

              // Gets the value stored within the `balances` mapping of the contract
            await token.getBalance(accounts[0], function (error, balance) {
                if (error) {
                    console.log(error);
                    $("#wbis_amount").html(error.message);
                } else {
                    //console.log(balance / 1E8);
                    $("#wbis_amount").html(balance / 1E8);
                }
            });
        }
      );
      await token.showTotal();
};


if (typeof Contracts === "undefined") var Contracts = { Token: { abi: [] } };
var token = new Token(Contracts["wbis"]);

