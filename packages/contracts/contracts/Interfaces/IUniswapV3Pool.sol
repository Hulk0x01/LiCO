// SPDX-License-Identifier: MIT
pragma solidity 0.6.11;

import './IUniswapV3PoolState.sol';
import './IUniswapV3PoolDerivedState.sol';

/// @title The interface for a UniswapV3 Pool
/// @notice A UniswapV3 pool facilitates swapping and automated market making between any two assets that strictly conform
/// to the ERC20 specification
/// @dev The pool interface is broken up into many smaller pieces
interface IUniswapV3Pool is IUniswapV3PoolState, IUniswapV3PoolDerivedState {}
