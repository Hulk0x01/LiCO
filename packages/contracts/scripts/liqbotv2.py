import os
import time
import logging
import argparse
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.exceptions import ContractLogicError
from eth_account import Account
from eth_account.account import LocalAccount
from eth_utils import function_signature_to_4byte_selector, remove_0x_prefix
from eth_abi import encode_abi
from utils import load_yaml


def config_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d (%(levelname)s): %(message)s",
        datefmt="%y-%m-%d %H:%M:%S"
    )

    logging.getLogger().setLevel(logging.INFO)


if __name__ == '__main__':
    config_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--network", default="testnet", choices=["testnet", "mainnet"])
    args = parser.parse_args()

    load_dotenv()
    account: LocalAccount = Account.from_key(os.environ['pk'])
    logging.info(f"account: {account.address}")

    config = load_yaml()
    contracts_address = config['contracts'][args.network]
    w3 = Web3(Web3.HTTPProvider(config['networks'][args.network]['rpc']))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    fn_selector = Web3.toHex(function_signature_to_4byte_selector("liquidate(uint256)"))
    params = Web3.toHex(encode_abi(["uint256"], [20]))
    tx_data = fn_selector + remove_0x_prefix(params)

    while True:
        tx = {
            'from': account.address,
            'to': contracts_address['liqBot'],
            'value': 0,
            'chainId': w3.eth.chain_id,
            'nonce': w3.eth.get_transaction_count(account.address),
            'data': tx_data
        }
        try:
            gas = w3.eth.estimate_gas(tx)
            tx['gas'] = gas
            tx['gasPrice'] = Web3.toWei(31, 'gwei')
            signed_tx = account.sign_transaction(tx)
            w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_receipt = w3.eth.wait_for_transaction_receipt(signed_tx.hash)
            logging.info(f"liquidation tx hash: {tx_receipt['transactionHash'].hex()}")
        except ContractLogicError as e:
            logging.error(e)
        time.sleep(5)
