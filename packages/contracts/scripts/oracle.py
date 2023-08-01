from web3 import Web3
from brownie import *


def main():
    current_price = 0.9
    prev_price = 0.95

    pk = "5aea27fd2b8c4a7ceccf32a8ab3ac130c2be885bcbcd533f6498d045af55c672"
    accounts.add(pk)
    mock_oracle = MockCoreOracle.at("0x91B851bD41C370C3ddFDf84D78F53583321cd47C")
    mock_oracle.setCurrentCorePrice(Web3.toWei(current_price, 'ether'), {'from': accounts[-1]})
    mock_oracle.setPrevCorePrice(Web3.toWei(prev_price, 'ether'), {'from': accounts[-1]})
