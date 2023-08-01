import os
from dotenv import load_dotenv
from brownie import *
from web3 import Web3
from hexbytes import HexBytes
from eth_utils import remove_0x_prefix

MAX_BYTES_32 = f"0x{'f' * 64}"
LP_REWARD_DURATION = 3 * 30 * 24 * 3600


def main():
    load_dotenv()
    pk = os.environ['pk']
    accounts.add(pk)
    deployer = accounts[-1]

    tx_kwargs = {'from': deployer}

    publish_source = config['networks'][network.show_active()]['verify']

    if network.show_active() == 'core-main':
        WCORE = "0x191E94fa59739e188dcE837F7f6978d84727AD01"
        switchboard_address = "0x73d6C66874e570f058834cAA666b2c352F1C792D"
        aggregator_address = "0x675a592a212C6659C41BeEf7f74c013d2AeDd5fb"
        uniswapV3_pool_address = "0xC4741661F610687Fe410e61E745f62005bd552F5"
        UNI_FACTORY = "0xe0b8838e8d73ff1CA193E8cc2bC0Ebf7Cf86F620"
        # https://docs.archerswap.finance/developer-resources/smart-contracts
        INIT_CODE_HASH = "0xa496ce5b8348c4a27befb2616addacbfdd5beaf87f2e951c1f8910fd0d3bf9c0"
    else:
        WCORE = "0xf6077b8DAcEc85be11d8D2dA04e1705668985Bcf"
        switchboard_address = "0xB27eB427A3675956Cdc2600d387F8d8aa44433CC"

        # deploy mock core oracle
        # core_oracle = MockCoreOracle.deploy(tx_kwargs, publish_source=True)
        # core_oracle.setCurrentCorePrice(867191827995000000)
        # core_oracle.setPrevCorePrice(857191827995000000)
        # core_oracle.setIntervalId(3)
        # switchboard_address = core_oracle.address

        aggregator_address = "0x17c8F53FFbB84745e7378E921ED637A88330203F"
        uniswapV3_pool_address = "0xC4741661F610687Fe410e61E745f62005bd552F5"
        UNI_FACTORY = "0x46b0077ac15af1DECF8eFF5727617419C98f5571"
        INIT_CODE_HASH = "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f"

    # deploy core contracts
    price_feed = PriceFeed.deploy(tx_kwargs)
    sorted_troves = SortedTroves.deploy(tx_kwargs)
    trove_manager = TroveManager.deploy(tx_kwargs)
    active_pool = ActivePool.deploy(tx_kwargs)
    stability_pool = StabilityPool.deploy(tx_kwargs)
    gas_pool = GasPool.deploy(tx_kwargs)
    default_pool = DefaultPool.deploy(tx_kwargs)
    coll_surplus_pool = CollSurplusPool.deploy(tx_kwargs)
    borrower_operations = BorrowerOperations.deploy(tx_kwargs, publish_source=publish_source)
    hint_helpers = HintHelpers.deploy(tx_kwargs)
    cusd_token = LUSDToken.deploy(
        trove_manager.address, stability_pool.address, borrower_operations.address, tx_kwargs)

    # calc cusd/core lp token address
    cusd_core_lp_token_address = calc_uniswap_v2_lp_address(cusd_token.address, WCORE, UNI_FACTORY, INIT_CODE_HASH)
    print(f"CUSD/CORE lp address: {cusd_core_lp_token_address}")

    # deploy uni pool
    uni_pool = Unipool.deploy(tx_kwargs)

    # deploy LICO contracts
    lico_staking = LQTYStaking.deploy(tx_kwargs)
    lockup_contract_factory = LockupContractFactory.deploy(tx_kwargs)
    community_issuance = CommunityIssuance.deploy(tx_kwargs)
    lico_token = LQTYToken.deploy(
        community_issuance.address, lico_staking.address, lockup_contract_factory.address,
        os.environ['bountyAddress'], uni_pool.address, os.environ['multisigAddress'],
        tx_kwargs
    )

    # deploy proxy scripts

    # deploy helper contracts
    MultiTroveGetter.deploy(trove_manager.address, sorted_troves.address, tx_kwargs)

    # Connect contracts to their dependencies
    sorted_troves.setParams(MAX_BYTES_32, trove_manager.address, borrower_operations.address, tx_kwargs)
    trove_manager.setAddresses(
        borrower_operations.address,
        active_pool.address,
        default_pool.address,
        stability_pool.address,
        gas_pool.address,
        coll_surplus_pool.address,
        price_feed.address,
        cusd_token.address,
        sorted_troves.address,
        lico_token.address,
        lico_staking.address,
        tx_kwargs
    )

    borrower_operations.setAddresses(
        trove_manager.address,
        active_pool.address,
        default_pool.address,
        stability_pool.address,
        gas_pool.address,
        coll_surplus_pool.address,
        price_feed.address,
        sorted_troves.address,
        cusd_token.address,
        lico_staking.address,
        tx_kwargs
    )

    stability_pool.setAddresses(
        borrower_operations.address,
        trove_manager.address,
        active_pool.address,
        cusd_token.address,
        sorted_troves.address,
        price_feed.address,
        community_issuance.address,
        tx_kwargs
    )

    active_pool.setAddresses(
        borrower_operations.address,
        trove_manager.address,
        stability_pool.address,
        default_pool.address,
        tx_kwargs
    )

    default_pool.setAddresses(trove_manager.address, active_pool.address, tx_kwargs)

    coll_surplus_pool.setAddresses(
        borrower_operations.address,
        trove_manager.address,
        active_pool.address,
        tx_kwargs
    )

    hint_helpers.setAddresses(sorted_troves.address, trove_manager.address, tx_kwargs)

    lockup_contract_factory.setLQTYTokenAddress(lico_token.address, tx_kwargs)

    lico_staking.setAddresses(
        lico_token.address,
        cusd_token.address,
        trove_manager.address,
        borrower_operations.address,
        active_pool.address,
        tx_kwargs
    )

    community_issuance.setAddresses(lico_token.address, stability_pool.address, tx_kwargs)

    uni_pool.setParams(lico_token.address, cusd_core_lp_token_address, LP_REWARD_DURATION, tx_kwargs)

    price_feed.setAddress(switchboard_address, aggregator_address, uniswapV3_pool_address, tx_kwargs)
    price_feed.fetchPrice(tx_kwargs)
    print(price_feed.lastGoodPrice())


def calc_uniswap_v2_lp_address(token_a: str, token_b: str, factory_address: str, init_code_hash: str) -> str:
    token_a = Web3.toChecksumAddress(token_a)
    token_b = Web3.toChecksumAddress(token_b)
    factory_address = Web3.toChecksumAddress(factory_address)
    token0, token1 = sort_tokens(token_a, token_b)
    token_packed: HexBytes = Web3.solidityKeccak(['address', 'address'], [token0, token1])
    lp_address = Web3.solidityKeccak(
        ['bytes'],
        ['0xff' + remove_0x_prefix(factory_address) + remove_0x_prefix(token_packed.hex()) + remove_0x_prefix(init_code_hash)]
    ).hex()[26:]
    return '0x' + lp_address


def sort_tokens(token_a: str, token_b: str) -> (str, str):
    assert token_a != token_b
    token0, token1 = (token_a, token_b) if token_a < token_b else (token_b, token_a)
    assert token0 != ZERO_ADDRESS
    return token0, token1


def deploy_liqBot():
    load_dotenv()
    accounts.add(os.environ['pk'])
    deployer = accounts[-1]
    print(f"deployer: {deployer.address}")

    LiqBot.deploy(
        "0x0C36139a2548a03fFA0948dFA4140aD0eCA9b613",
        "0x9A751278F2dEdFbA68897d4B6f2Dc73048F914Be",
        "0xE6B4840A55DdD5a07b6de76b3c33b03535F0FF27",
        "0xdE01b68554032B6dd79A60d5bdF7793Dee17065c",
        {'from': deployer}
    )
