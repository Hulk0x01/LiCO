// SPDX-License-Identifier: MIT
pragma solidity 0.6.11;
import "../Interfaces/IPriceFeed.sol";
import "../Interfaces/ITroveManager2.sol";
import "../Interfaces/ISortedTroves.sol";
import "../Interfaces/ILUSDToken.sol";


contract LiqBot {
    IPriceFeed public priceFeed;
    ITroveManager2 public troveManager;
    ISortedTroves public sortedTroves;
    ILUSDToken public lusdToken;
    address public owner;

    event Received(address, uint);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event liquidateTroves(uint num);

    constructor(
        address _priceFeedAddress,
        address _troveManagerAddress,
        address _sortedTrovesAddress,
        address _cusdTokenAddress
    ) public {
        priceFeed = IPriceFeed(_priceFeedAddress);
        troveManager = ITroveManager2(_troveManagerAddress);
        sortedTroves = ISortedTroves(_sortedTrovesAddress);
        lusdToken = ILUSDToken(_cusdTokenAddress);
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Ownable: caller is not the owner");
        _;
    }

    receive() external payable {
        emit Received(msg.sender, msg.value);
    }

    function changeOwner(address newOwner) external onlyOwner {
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function withdrawCore() onlyOwner public {
        msg.sender.transfer(address(this).balance);
    }

    function withdrawStableCoin() onlyOwner public {
        lusdToken.transfer(msg.sender, lusdToken.balanceOf(address(this)));
    }

    function withdrawAll() onlyOwner external {
        withdrawCore();
        withdrawStableCoin();
    }

    function liquidate(uint maxNum) external {
        require(maxNum > 0, "MaxNum should large than 0");
        uint price = priceFeed.fetchPrice();
        bool isRecoveryMode = troveManager.checkRecoveryMode(price);
        uint lcr;
        if (isRecoveryMode == true) {
            lcr = troveManager.CCR();
        } else {
            lcr = troveManager.MCR();
        }
        uint n;
        address latestTrove = sortedTroves.getLast();
        if (latestTrove != address(0) && troveManager.getCurrentICR(latestTrove, price) <= lcr) {
            n++;
            address currentTrove = latestTrove;
            while (true) {
                if (n >= maxNum) break;
                address _trove = sortedTroves.getPrev(currentTrove);
                if (_trove == address(0)) break;
                if (troveManager.getCurrentICR(_trove, price) > lcr) break;
                n++;
                currentTrove = _trove;
            }
        }
        require(n > 0, "No trove eligible for liquidation");
        troveManager.liquidateTroves(n);
        emit liquidateTroves(n);
    }
}
