// SPDX-License-Identifier: MIT
pragma solidity 0.6.11;
import "../Interfaces/ISwitchboard.sol";
import "../Dependencies/Ownable.sol";

contract MockCoreOracle is ISwitchboard, Ownable {
    int256 public currentCorePrice;
    int256 public prevCorePrice;
    uint80 public intervalId;

    function latestResult(address aggregatorAddress) external override payable returns(int256, uint) {
        return (currentCorePrice, block.timestamp - 60);
    }

    function getCurrentIntervalId(address aggregatorAddress) external override view returns(uint80) {
        return intervalId;
    }

    function getIntervalResult(address aggregatorAddress, uint80 round)
        external
        override
        view
        returns(int256, uint256, uint256){
        return (prevCorePrice, block.timestamp - 180, block.timestamp - 90);
    }

    function setCurrentCorePrice(int256 _currentCorePrice) public onlyOwner {
        currentCorePrice = _currentCorePrice;
    }

    function setPrevCorePrice(int256 _prevCorePrice) public onlyOwner {
        prevCorePrice = _prevCorePrice;
    }

    function setIntervalId(uint80 _intervalId) public onlyOwner {
        intervalId = _intervalId;
    }
}
