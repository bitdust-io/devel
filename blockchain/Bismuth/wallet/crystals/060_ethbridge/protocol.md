# Temp doc - Bridge protocol

# BIS to wBIS

## Send BIS to bridge

- Bis Recipient is the bridge address
- Amount is the BIS amount (fees will be deducted, min 10 BIS)
- Operation is "ethbridge:send"
- Data is the recipient ETH address, 0x... 

## Retrieve SIG

Once the BIS tx has BIS conf confirmations, the proxy mint tx can be signed.

The bridge sends a BIS tx with the signature
 
- Bis recipient is the initial BIS sender
- Amount is 0
- Operation is "ethbridge:signature"
- Data is bistxidhash(hex):signature(0x....):amount(int format, original - fees)



## Proxymint wBIS

The user proxy mints his wBIS from the sig

ETH Oracle sees the eth tx and posts to BIS once ETH conf passed.  
(oracle verifies this is a legit mint tx, and matches with txid hash)

- Bis recipient is the initial bis sender data
- Amount is 0
- Operation is "ethbridge:proxymint"
- Data is bistxidhash(hex):eth_txid(0x):eth_recipient (0x):minted amount(int format, original -fees)


# wBIS to BIS

## Burn wBIS on ETH

ETH Oracle sees the eth tx and posts to BIS once ETH conf passed.  
(oracle verifies this is a legit burn tx)

- Bis recipient is the ETH burn data (bis address)
- Amount is 0
- Operation is "ethbridge:burn"
- Data is ETH txid 0x...:tx_block_height:eth_block_height:eth_sender 0x:the amount 1000000000 (int format)

## Send native BIS

ETH Bridge sees the oracle, sends the amount to the recipient if the ETH tx_id was not sent yet

- Bis recipient is the ETH burn data (bis address)
- Amount is the BIS amount (burned - fees)
- Operation is "ethbridge:deliver"
- Data is ETH txid 0x...
 
 
# Current ETH block

ETH Oracle regularly transmits the current ETH block

- Bis recipient is the ETH Oracle address
- Amount is 0
- Operation is "ethbridge:height"
- Data is ETH block height at that time

The frequency of this update is to be decided. Should be at least once per hour.

 
# Legal terms

Update the Bridge legal terms.

- Bis recipient is the ETH Bridge address
- Amount is 0
- Operation is "ethbridge:terms"
- Data is the terms as text.
 
