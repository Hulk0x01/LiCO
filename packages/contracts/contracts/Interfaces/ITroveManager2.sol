// SPDX-License-Identifier: MIT
pragma solidity 0.6.11;
import "./ITroveManager.sol";

interface ITroveManager2 is ITroveManager {
    function CCR() external view returns(uint);
    function MCR() external view returns(uint);
}
