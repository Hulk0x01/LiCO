// SPDX-License-Identifier: MIT

pragma solidity 0.6.11;

import "./Interfaces/ISwitchboard.sol";
import "./Interfaces/IPriceFeed.sol";
import "./Interfaces/IUniswapV3Pool.sol";
import "./Dependencies/SafeMath.sol";
import "./Dependencies/Ownable.sol";
import "./Dependencies/CheckContract.sol";
import "./Dependencies/BaseMath.sol";
import "./Dependencies/LiquityMath.sol";
import "./Dependencies/TickMath.sol";
import "./Dependencies/FullMath.sol";

/*
* PriceFeed for mainnet deployment, to be connected to Chainlink's live ETH:USD aggregator reference 
* contract, and a wrapper contract TellorCaller, which connects to TellorMaster contract.
*
* The PriceFeed uses Chainlink as primary oracle, and Tellor as fallback. It contains logic for
* switching oracles based on oracle failures, timeouts, and conditions for returning to the primary
* Chainlink oracle.
*/
contract PriceFeed is Ownable, BaseMath, CheckContract,  IPriceFeed {
    using SafeMath for uint256;
    string constant public NAME = "PriceFeed";

    // Maximum time period allowed since Switchboard's latest round data timestamp, beyond which Switchboard is considered frozen.
    uint constant public TIMEOUT = 3600;  // 1 hours: 60 * 60 * 1

    // Maximum deviation allowed between two consecutive Switchboard oracle prices. 18-digit precision.
    uint constant public MAX_PRICE_DEVIATION_FROM_PREVIOUS_ROUND =  5e17; // 50%

    uint32 constant public TWAP_INTERVAL = 60;
    uint constant public PRICE_DECIMAL = 1e12 * 1e18;

    address public switchboardAddress;
    address public aggregatorAddress;
    IUniswapV3Pool public uniswapV3Pool;

    // The last good price seen from an oracle by Liquity
    uint public lastGoodPrice;

    struct SwitchboardResponse {
        uint256 value;
        uint256 timestamp;
    }

    event LastGoodPriceUpdated(uint _lastGoodPrice);

    function setAddress(
        address _switchboardAddress,
        address _aggregatorAddress,
        address _uniswapV3PoolAddress
    ) external onlyOwner {
        checkContract(_switchboardAddress);
        checkContract(_uniswapV3PoolAddress);

        switchboardAddress = _switchboardAddress;
        aggregatorAddress = _aggregatorAddress;
        uniswapV3Pool = IUniswapV3Pool(_uniswapV3PoolAddress);

        SwitchboardResponse memory switchboardResponse = _getCurrentSwitchboardResponse();
        SwitchboardResponse memory prevSwitchboardResponse = __getPrevSwitchboardResponse(
            ISwitchboard(switchboardAddress).getCurrentIntervalId(aggregatorAddress)
        );

        require(!_switchboardIsBroken(switchboardResponse, prevSwitchboardResponse)
            && !_switchboardIsFrozen(switchboardResponse),
            "PriceFeed: Switchboard must be working and current"
        );

         _renounceOwnership();
    }

    function fetchPrice() external override returns(uint) {
        SwitchboardResponse memory switchboardResponse = _getCurrentSwitchboardResponse();
        SwitchboardResponse memory prevSwitchboardResponse = __getPrevSwitchboardResponse(
            ISwitchboard(switchboardAddress).getCurrentIntervalId(aggregatorAddress)
        );

        bool switchboardRespIsBroken = _switchboardIsBroken(switchboardResponse, prevSwitchboardResponse);
        bool switchboardRespIsFrozen = _switchboardIsFrozen(switchboardResponse);
        bool switchboardRespUntrusted = _switchboardPriceChangeAboveMax(switchboardResponse, prevSwitchboardResponse);

        if (switchboardRespIsBroken || switchboardRespIsFrozen || switchboardRespUntrusted) {
            return _storeUniswapV3Price(_getUniswapV3Response());
        } else {
            return _storeSwitchboardPrice(switchboardResponse);
        }
    }

    function _switchboardIsBroken(
        SwitchboardResponse memory _currentResponse,
        SwitchboardResponse memory _prevResponse
    ) internal view returns(bool) {
        return _badSwitchboardResponse(_currentResponse) || _badSwitchboardResponse(_prevResponse);
    }

    function _badSwitchboardResponse(SwitchboardResponse memory _response) internal view returns(bool) {
        if (_response.timestamp == 0 || _response.timestamp > block.timestamp) {return true;}
        if (_response.value == 0) {return true;}
        return false;
    }

    function _switchboardIsFrozen(SwitchboardResponse memory _response) internal view returns(bool) {
        return block.timestamp.sub(_response.timestamp) > TIMEOUT;
    }

    function _getCurrentSwitchboardResponse() internal returns (SwitchboardResponse memory switchboardResponse) {
        try ISwitchboard(switchboardAddress).latestResult(aggregatorAddress) returns
        (
            int256 value,
            uint256 timestamp
        ) {
            if (value < 0) {return switchboardResponse;}
            switchboardResponse.value = uint(value);
            switchboardResponse.timestamp = timestamp;
            return switchboardResponse;
        } catch {
            return switchboardResponse;
        }
    }

    function __getPrevSwitchboardResponse(uint80 _currentRoundId) internal view
        returns (SwitchboardResponse memory switchboardResponse) {
        if (_currentRoundId == 0) {return switchboardResponse;}

        try ISwitchboard(switchboardAddress).getIntervalResult(aggregatorAddress, _currentRoundId - 1) returns
        (
            int256 value,
            uint256 timestamp,
            uint256 
        ) {
            if (value < 0) {return switchboardResponse;}
            switchboardResponse.value = uint(value);
            switchboardResponse.timestamp = timestamp;
            return switchboardResponse;
        } catch {
            return switchboardResponse;
        }
    }

    function _storeSwitchboardPrice(SwitchboardResponse memory _response) internal returns(uint) {
        lastGoodPrice = uint(_response.value);
        emit LastGoodPriceUpdated(lastGoodPrice);
        return lastGoodPrice;
    }

    function _storeUniswapV3Price(uint _price) internal returns(uint) {
        lastGoodPrice = _price;
        emit LastGoodPriceUpdated(lastGoodPrice);
        return lastGoodPrice;
    }

    function _switchboardPriceChangeAboveMax(
        SwitchboardResponse memory _currentResponse,
        SwitchboardResponse memory _prevResponse
    ) internal pure returns(bool) {
        uint currentPrice = _currentResponse.value;
        uint prevPrice = _prevResponse.value;

        uint minPrice = LiquityMath._min(currentPrice, prevPrice);
        uint maxPrice = LiquityMath._max(currentPrice, prevPrice);

        /*
        * Use the larger price as the denominator:
        * - If price decreased, the percentage deviation is in relation to the the previous price.
        * - If price increased, the percentage deviation is in relation to the current price.
        */
        uint percentDeviation = maxPrice.sub(minPrice).mul(DECIMAL_PRECISION).div(maxPrice);

        // Return true if price has more than doubled, or more than halved.
        return percentDeviation > MAX_PRICE_DEVIATION_FROM_PREVIOUS_ROUND;
    }

    function _getUniswapV3Response() internal view returns(uint256) {
        return getUniswapV3ResponseWithCustomInterval(TWAP_INTERVAL);
    }

    function getUniswapV3ResponseWithCustomInterval(uint32 _twapInterval) public view returns(uint256) {
        uint160 sqrtPriceX96;
        if (_twapInterval == 0) {
            (sqrtPriceX96, , , , , , ) = uniswapV3Pool.slot0();
        } else {
            uint32[] memory secondsAgos = new uint32[](2);
            secondsAgos[0] = _twapInterval; // from (before)
            secondsAgos[1] = 0; // to (now)
            (int56[] memory tickCumulatives, ) = uniswapV3Pool.observe(secondsAgos);
            // tick to sqrt price
            sqrtPriceX96 = TickMath.getSqrtRatioAtTick(
                int24((tickCumulatives[1] - tickCumulatives[0]) / _twapInterval)
            );
        }
        // sqrt price to price
//        return PRICE_DECIMAL.div(FullMath.mulDiv(sqrtPriceX96, sqrtPriceX96, 1 << 192));

        // according to https://blog.uniswap.org/uniswap-v3-math-primer#how-do-i-calculate-the-current-exchange-rate
        return SafeMath.mul(sqrtPriceX96, sqrtPriceX96).mul(1e24).div(1 << 192).mul(1e6);
    }
}
