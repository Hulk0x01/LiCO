import os
import logging
import math
from random import randint
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
    parser.add_argument("-m", "--amount", type=float)
    parser.add_argument("-i", "--iterations", default=50, type=int)
    parser.add_argument("-f", "--fee", default=1, type=float)
    args = parser.parse_args()

    cusd_amount = Web3.toWei(args.amount, 'ether')
    assert cusd_amount > 0
    max_iterations = args.iterations
    assert 0.5 <= args.fee <= 5
    max_fee = Web3.toWei(args.fee, 'ether')

    load_dotenv()
    account: LocalAccount = Account.from_key(os.environ['pk'])
    logging.info(f"account: {account.address}")

    config = load_yaml()
    contracts_address = config['contracts'][args.network]
    w3 = Web3(Web3.HTTPProvider(config['networks'][args.network]['rpc']))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    sorted_troves = w3.eth.contract(contracts_address['sorted-troves'], abi=load_abi("SortedTroves"))
    hint_helps = w3.eth.contract(contracts_address['hint-helps'], abi=load_abi("HintHelpers"))
    trove_manager = w3.eth.contract(contracts_address['trove-manager'], abi=load_abi("TroveManager"))
    price_feed = w3.eth.contract(contracts_address['price-feed'], abi=load_abi("PriceFeed"))
    cusd = w3.eth.contract(contracts_address['cusd'], abi=load_abi("LUSDToken"))

    logging.info(f"cusd balance: {Web3.fromWei(cusd.functions.balanceOf(account.address).call(), 'ether')}")

    fetch_price_tx = price_feed.functions.fetchPrice().build_transaction({
        "gasPrice": Web3.toWei(31, 'gwei'),
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
        "from": account.address
    })
    signed_tx = account.sign_transaction(fetch_price_tx)
    w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed_tx.rawTransaction))

    core_price = price_feed.functions.lastGoodPrice().call()
    logging.info(f"core price: {core_price}")
    first_redemption_hint, partial_redemption_new_ICR, truncated_cusd_amount = \
        hint_helps.functions.getRedemptionHints(cusd_amount, core_price, max_iterations).call()
    logging.info(
        f"first_redemption_hint: {first_redemption_hint}, "
        f"partial_redemption_new_ICR: {partial_redemption_new_ICR},"
        f"truncated_cusd_amount: {truncated_cusd_amount}")

    approx_partial_redemption_hint = hint_helps.functions.getApproxHint(
        partial_redemption_new_ICR,
        int(15 * math.sqrt(sorted_troves.functions.getSize().call())),
        randint(0, 100)
    ).call()[0]
    logging.info(f"approx_partial_redemption_hint: {approx_partial_redemption_hint}")

    exact_partial_redemption_hint = sorted_troves.functions.findInsertPosition(
        partial_redemption_new_ICR,
        approx_partial_redemption_hint,
        approx_partial_redemption_hint
    ).call()
    logging.info(f"exact_partial_redemption_hint: {exact_partial_redemption_hint}")

    unsigned_tx = trove_manager.functions.redeemCollateral(
        truncated_cusd_amount,
        first_redemption_hint,
        exact_partial_redemption_hint[0],
        exact_partial_redemption_hint[1],
        partial_redemption_new_ICR,
        0, max_fee
    ).build_transaction({
        "gasPrice": Web3.toWei(31, 'gwei'),
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
        "from": account.address
    })
    signed_tx = account.sign_transaction(unsigned_tx)
    tx = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    logging.info(f"redeem collateral tx: {tx.hex()}")


