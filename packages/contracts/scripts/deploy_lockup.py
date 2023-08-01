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
    parser.add_argument("-b", "--beneficiary", type=str)
    parser.add_argument("-t", "--unlockTime", type=int)
    args = parser.parse_args()

    load_dotenv()
    account: LocalAccount = Account.from_key(os.environ['pk'])
    logging.info(f"account: {account.address}")

    config = load_yaml()
    contracts_address = config['contracts'][args.network]
    w3 = Web3(Web3.HTTPProvider(config['networks'][args.network]['rpc']))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    lockup_contract_factory = w3.eth.contract(contracts_address['lockup-contract-factory'], abi=load_abi("LockupContractFactory"))

    unsigned_tx = lockup_contract_factory.functions.deployLockupContract(
        args.beneficiary, args.unlockTime
    ).build_transaction({
        "gasPrice": Web3.toWei(31, 'gwei'),
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
        "from": account.address
    })
    signed_tx = account.sign_transaction(unsigned_tx)
    tx = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    logging.info(f"tx: {tx.hex()}")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx)
    log = lockup_contract_factory.events.LockupContractDeployedThroughFactory().processLog(tx_receipt['logs'][1])
    logging.info(f"lockupContractAddress: {log['args']['_lockupContractAddress']}")

