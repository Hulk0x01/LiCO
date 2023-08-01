import time
import os
import logging
from web3 import Web3
from web3.constants import ADDRESS_ZERO
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
    args = parser.parse_args()

    load_dotenv()
    account: LocalAccount = Account.from_key(os.environ['pk'])
    logging.info(f"account: {account.address}")

    config = load_yaml()
    contracts_address = config['contracts'][args.network]
    w3 = Web3(Web3.HTTPProvider(config['networks'][args.network]['rpc']))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    sorted_troves = w3.eth.contract(contracts_address['sorted-troves'], abi=load_abi("SortedTroves"))
    trove_manager = w3.eth.contract(contracts_address['trove-manager'], abi=load_abi("TroveManager"))
    price_feed = w3.eth.contract(contracts_address['price-feed'], abi=load_abi("PriceFeed"))

    while True:
        latest_core_price = price_feed.functions.lastGoodPrice().call()
        is_recovery_mode = trove_manager.functions.checkRecoveryMode(latest_core_price).call()
        logging.info(f"is recovery mode: {is_recovery_mode}, core price: {latest_core_price}")
        if is_recovery_mode:
            lcr = trove_manager.functions.CCR().call()
        else:
            lcr = trove_manager.functions.MCR().call()

        n = 0
        pending_liquidation_troves = []
        latest_trove = sorted_troves.functions.getLast().call()
        if latest_trove != ADDRESS_ZERO and trove_manager.functions.getCurrentICR(latest_trove, latest_core_price).call() <= lcr:
            n += 1
            pending_liquidation_troves.append(latest_trove)
            current_trove = latest_trove
            while True:
                _trove = sorted_troves.functions.getPrev(current_trove).call()
                if _trove == ADDRESS_ZERO:
                    break
                if trove_manager.functions.getCurrentICR(_trove, latest_core_price).call() > lcr:
                    break
                n += 1
                pending_liquidation_troves.append(_trove)
                current_trove = _trove
        if n > 0:
            unsigned_tx = trove_manager.functions.liquidateTroves(n).build_transaction({
                "gasPrice": Web3.toWei(31, 'gwei'),
                "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": w3.eth.chain_id,
                "from": account.address
            })
            signed_tx = account.sign_transaction(unsigned_tx)
            tx = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logging.info(f"liquidation tx: {tx.hex()}")
        # for trove in pending_liquidation_troves:
        #     unsigned_tx = trove_manager.functions.liquidate(trove).build_transaction({
        #         "gasPrice": Web3.toWei(31, 'gwei'),
        #         "nonce": w3.eth.get_transaction_count(account.address),
        #         "chainId": w3.eth.chain_id,
        #         "from": account.address
        #     })
        #     signed_tx = account.sign_transaction(unsigned_tx)
        #     tx = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        #     logging.info(f"liquidation tx: {tx.hex()}")
        time.sleep(5)
