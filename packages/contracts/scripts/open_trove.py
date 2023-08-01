import os
import logging
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.account import LocalAccount
import argparse
from dotenv import load_dotenv
from utils import load_yaml, load_abi, config_logging


if __name__ == '__main__':
    config_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--network", default="testnet", choices=["testnet", "mainnet"])
    parser.add_argument("-c", "--collateral", type=int)
    parser.add_argument("-d", "--debt", type=int)

    args = parser.parse_args()

    load_dotenv()
    account: LocalAccount = Account.from_key(os.environ['pk'])
    logging.info(f"account: {account.address}")

    config = load_yaml()
    contracts_address = config['contracts'][args.network]
    w3 = Web3(Web3.HTTPProvider(config['networks'][args.network]['rpc']))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    borrow_operation = w3.eth.contract(contracts_address['borrow-operation'], abi=load_abi("BorrowerOperations"))

    unsigned_tx = borrow_operation.functions.openTrove(
        Web3.toWei(0.5, 'ether'),
        Web3.toWei(args.debt, 'ether'),
        account.address,
        account.address
    ).build_transaction({
        "gasPrice": Web3.toWei(31, 'gwei'),
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
        "value": Web3.toWei(args.collateral, 'ether'),
        "from": account.address
    })
    signed_tx = account.sign_transaction(unsigned_tx)
    tx = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    logging.info(f"open trove tx: {tx.hex()}")

