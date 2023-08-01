import os
from dotenv import load_dotenv
from brownie import *


def main():
    load_dotenv()
    pk = os.environ['pk']
    accounts.add(pk)
    deployer = accounts[-1]

    if network.show_active() == 'core-main':
        switchboard_address = "0x73d6C66874e570f058834cAA666b2c352F1C792D"
        aggregator_address = "0x675a592a212C6659C41BeEf7f74c013d2AeDd5fb"
        price_feed_address = "0x3C6a8814070A5550c3C04793a2bB9B898272B8CA"
        uniswapV3_pool_address = "0xC4741661F610687Fe410e61E745f62005bd552F5"
    else:
        switchboard_address = "0x1bAB46734e02d25D9dF5EE725c0646b39C0c5224"
        aggregator_address = "0x27fB4C1cF4315760d37edCe61cf838Ed42C791d8"
        price_feed_address = "0x0379dFBcc4dD090d06fc58130d82f9560E58C3AB"
        uniswapV3_pool_address = "0xC4741661F610687Fe410e61E745f62005bd552F5"

    # c = PriceFeed.deploy({'from': deployer})
    c = PriceFeed.at(price_feed_address)
    c.setAddress(switchboard_address, aggregator_address, uniswapV3_pool_address, {'from': deployer})
    c.fetchPrice({'from': deployer})
    print(c.lastGoodPrice())
