/**
 * Deterministic PAPER ledger. All stored money uses integer microdollars
 * (1 USD = 1,000,000 units), including prices such as $0.051.
 * Quotes, total fees, transaction IDs, timestamps and official outcomes are
 * supplied by the caller. This module never invents a price or a fee schedule.
 * Browser persistence is suitable for previews; a server must own member ledgers.
 */
export const MONEY_SCALE = 1000000;
export const STARTING_BALANCE = 100;
export const DEFAULT_ENTRY_BUDGET = 25;
export const SUPPORTED_ASSETS = Object.freeze(['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']);

export class PracticeError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'PracticeError';
    this.code = code;
  }
}

function fail(code, message) { throw new PracticeError(code, message); }
function safeInteger(value, label, minimum = 0) {
  if (!Number.isSafeInteger(value) || value < minimum) {
    fail('INVALID_VALUE', `${label} must be a safe integer${minimum === 0 ? ' at least zero' : ''}.`);
  }
  return value;
}
function safeResult(value) {
  if (!Number.isSafeInteger(value)) fail('AMOUNT_TOO_LARGE', 'The amount is too large.');
  return value;
}
function identity(value, label) {
  if (typeof value !== 'string' || !value.trim() || value.trim().length > 240) {
    fail('INVALID_ID', `${label} is required.`);
  }
  return value.trim();
}
function sideValue(value) {
  if (value !== 'YES' && value !== 'NO') fail('INVALID_SIDE', 'Choose YES or NO.');
  return value;
}
function assetValue(value) {
  if (!SUPPORTED_ASSETS.includes(value)) fail('INVALID_ASSET', 'Choose a supported bot asset.');
  return value;
}

/** Exact nonnegative decimal conversion. Rejects excess precision and NaN. */
export function toMoneyUnits(value, label = 'Amount') {
  if (typeof value !== 'number' && typeof value !== 'string') {
    fail('INVALID_AMOUNT', `${label} must be a dollar amount.`);
  }
  if (typeof value === 'number' && !Number.isFinite(value)) {
    fail('INVALID_AMOUNT', `${label} must be finite.`);
  }
  const text = String(value).trim();
  const match = /^(\d+)(?:\.(\d{0,6}))?$/.exec(text);
  if (!match) fail('INVALID_AMOUNT', `${label} must be nonnegative with at most 6 decimal places.`);
  const units = BigInt(match[1]) * BigInt(MONEY_SCALE) + BigInt((match[2] || '').padEnd(6, '0'));
  if (units > BigInt(Number.MAX_SAFE_INTEGER)) fail('AMOUNT_TOO_LARGE', `${label} is too large.`);
  return Number(units);
}
export function fromMoneyUnits(units) { return safeResult(units) / MONEY_SCALE; }

/** Read-only view of completed transactions for one room, newest first.
 * The server ledger remains authoritative; no reconstructed entry prices.
 */
export function practiceTradeHistory(account, asset) {
  if (!SUPPORTED_ASSETS.includes(asset) || !Array.isArray(account?.transactions)) return [];
  const money = units => Number.isSafeInteger(units) ? fromMoneyUnits(units) : null;
  return account.transactions.filter(tx => tx && tx.asset === asset &&
    ['CLOSE', 'SETTLE'].includes(tx.type)).map(tx => ({
      id: tx.id, asset: tx.asset, side: tx.side, type: tx.type, timestamp: tx.timestamp,
      officialWinningSide: tx.officialWinningSide,
      costBasis: money(tx.costBasisUnits),
      exitPrice: money(tx.priceUnits),
      realizedPnl: money(tx.realizedPnlUnits),
      returnPct: Number.isSafeInteger(tx.costBasisUnits) && tx.costBasisUnits > 0 &&
        Number.isSafeInteger(tx.realizedPnlUnits) ? tx.realizedPnlUnits / tx.costBasisUnits * 100 : null,
    })).reverse();
}
function priceUnits(value, label, allowZero) {
  const units = toMoneyUnits(value, label);
  if (units > MONEY_SCALE || (!allowZero && units === 0)) {
    fail('INVALID_PRICE', `${label} must be ${allowZero ? 'between $0 and $1' : 'greater than $0 and no more than $1'}.`);
  }
  return units;
}
function multiply(units, quantity) {
  const result = BigInt(units) * BigInt(quantity);
  if (result > BigInt(Number.MAX_SAFE_INTEGER)) fail('AMOUNT_TOO_LARGE', 'The order is too large.');
  return Number(result);
}
function proportional(units, quantity, totalQuantity) {
  return Number(BigInt(units) * BigInt(quantity) / BigInt(totalQuantity));
}
function quantityValue(value) {
  if (!Number.isSafeInteger(value) || value <= 0) {
    fail('INVALID_QUANTITY', 'The number of contracts must be a positive whole number.');
  }
  return value;
}
function timestampValue(value) {
  if (value === undefined || value === null) return null;
  if ((typeof value === 'string' && value.length <= 80) ||
      (typeof value === 'number' && Number.isFinite(value))) return value;
  fail('INVALID_TIMESTAMP', 'A valid timestamp is required.');
}
function clone(account) { return JSON.parse(JSON.stringify(account)); }

export function createAccount({ userId = 'local-preview', attemptId = 'attempt-1' } = {}) {
  return {
    version: 1, mode: 'PAPER', currency: 'USD',
    userId: identity(userId, 'User ID'), attemptId: identity(attemptId, 'Attempt ID'), resetCount: 0,
    initialBalanceUnits: STARTING_BALANCE * MONEY_SCALE,
    cashUnits: STARTING_BALANCE * MONEY_SCALE,
    realizedPnlUnits: 0, totalFeesUnits: 0,
    positions: [], transactions: [], transactionIds: [],
  };
}

function validateAccount(account) {
  if (!account || account.version !== 1 || account.mode !== 'PAPER' || account.currency !== 'USD' ||
      account.initialBalanceUnits !== STARTING_BALANCE * MONEY_SCALE) {
    fail('INVALID_ACCOUNT', 'The practice account is invalid.');
  }
  identity(account.userId, 'User ID');
  identity(account.attemptId, 'Attempt ID');
  safeInteger(account.cashUnits, 'Cash');
  safeInteger(account.totalFeesUnits, 'Fees');
  safeInteger(account.resetCount, 'Reset count');
  safeResult(account.realizedPnlUnits);
  if (!Array.isArray(account.positions) || !Array.isArray(account.transactions) || !Array.isArray(account.transactionIds)) {
    fail('INVALID_ACCOUNT', 'The practice ledger is invalid.');
  }
  const positionIds = new Set();
  let basis = 0;
  for (const position of account.positions) {
    identity(position.id, 'Position ID');
    identity(position.contractId, 'Contract ID');
    assetValue(position.asset); sideValue(position.side); quantityValue(position.quantity);
    if (positionIds.has(position.id)) fail('INVALID_ACCOUNT', 'Duplicate positions in the ledger.');
    positionIds.add(position.id);
    safeInteger(position.entryGrossUnits, 'Entry amount', 1);
    safeInteger(position.entryFeeUnits, 'Entry fee');
    safeInteger(position.entryCostUnits, 'Cost basis', 1);
    if (position.entryCostUnits !== position.entryGrossUnits + position.entryFeeUnits) {
      fail('INVALID_ACCOUNT', 'The position cost basis does not balance.');
    }
    basis = safeResult(basis + position.entryCostUnits);
  }
  if (new Set(account.transactionIds).size !== account.transactionIds.length ||
      account.transactionIds.length !== account.transactions.length ||
      account.transactions.some((tx, i) => tx.id !== account.transactionIds[i])) {
    fail('INVALID_ACCOUNT', 'The transaction history is invalid.');
  }
  if (safeResult(account.cashUnits + basis) !== safeResult(account.initialBalanceUnits + account.realizedPnlUnits)) {
    fail('INVALID_ACCOUNT', 'The practice account does not balance.');
  }
  return account;
}

function requireNewTransaction(account, transactionId) {
  validateAccount(account);
  const id = identity(transactionId, 'Transaction ID');
  if (account.transactionIds.includes(id)) fail('DUPLICATE_TRANSACTION', 'This practice transaction was already recorded.');
  return id;
}

/** fee is the caller-supplied TOTAL order fee, not a per-contract fee. */
export function quotePurchase({ account, ask, budget = DEFAULT_ENTRY_BUDGET, fee = 0, quantity } = {}) {
  if (account) validateAccount(account);
  const askUnits = priceUnits(ask, 'Ask price', false);
  const budgetUnits = toMoneyUnits(budget, 'Budget');
  if (budgetUnits === 0) fail('INVALID_BUDGET', 'Choose a budget greater than zero.');
  const feeUnits = toMoneyUnits(fee, 'Total entry fee');
  const availableUnits = account ? account.cashUnits : budgetUnits;
  const effectiveBudgetUnits = Math.min(budgetUnits, availableUnits);
  const maxQuantity = effectiveBudgetUnits >= feeUnits ? Number(BigInt(effectiveBudgetUnits - feeUnits) / BigInt(askUnits)) : 0;
  if (maxQuantity < 1) fail('INSUFFICIENT_FUNDS', 'The available practice cash cannot cover one contract and its fee.');
  const count = quantity === undefined ? maxQuantity : quantityValue(quantity);
  if (count > maxQuantity) fail('INSUFFICIENT_BUDGET', 'The order exceeds the available cash or fee-inclusive budget.');
  const grossUnits = multiply(askUnits, count);
  const totalCostUnits = safeResult(grossUnits + feeUnits);
  return {
    quantity: count, maxQuantity, ask: fromMoneyUnits(askUnits),
    budget: fromMoneyUnits(budgetUnits), effectiveBudget: fromMoneyUnits(effectiveBudgetUnits),
    grossCost: fromMoneyUnits(grossUnits), fee: fromMoneyUnits(feeUnits), fees: fromMoneyUnits(feeUnits),
    totalCost: fromMoneyUnits(totalCostUnits), remainingCash: fromMoneyUnits(availableUnits - totalCostUnits),
    canAfford: true, askUnits, grossUnits, feeUnits, totalCostUnits,
    feePolicy: 'explicit-total-fee',
  };
}

export function buyContracts(account, options = {}) {
  const transactionId = requireNewTransaction(account, options.transactionId);
  const asset = assetValue(options.asset);
  const contractId = identity(options.contractId, 'Contract ID');
  const side = sideValue(options.side);
  const timestamp = timestampValue(options.timestamp);
  const quote = quotePurchase({ ...options, account });
  const next = clone(account);
  let position = next.positions.find(p => p.asset === asset && p.contractId === contractId && p.side === side);
  if (position) {
    position.quantity = safeResult(position.quantity + quote.quantity);
    position.entryGrossUnits = safeResult(position.entryGrossUnits + quote.grossUnits);
    position.entryFeeUnits = safeResult(position.entryFeeUnits + quote.feeUnits);
    position.entryCostUnits = safeResult(position.entryCostUnits + quote.totalCostUnits);
    position.updatedAt = timestamp;
  } else {
    position = {
      id: `pos:${next.transactions.length + 1}:${asset}:${side}`,
      asset, contractId, side, quantity: quote.quantity,
      entryGrossUnits: quote.grossUnits, entryFeeUnits: quote.feeUnits, entryCostUnits: quote.totalCostUnits,
      openedAt: timestamp, updatedAt: timestamp,
    };
    next.positions.push(position);
  }
  next.cashUnits -= quote.totalCostUnits;
  next.totalFeesUnits = safeResult(next.totalFeesUnits + quote.feeUnits);
  next.transactions.push({
    id: transactionId, type: 'BUY', asset, contractId, side, positionId: position.id,
    quantity: quote.quantity, priceUnits: quote.askUnits, grossUnits: quote.grossUnits,
    feeUnits: quote.feeUnits, costBasisUnits: quote.totalCostUnits,
    netCashChangeUnits: -quote.totalCostUnits, realizedPnlUnits: 0, timestamp,
  });
  next.transactionIds.push(transactionId);
  return validateAccount(next);
}

function getPosition(account, positionId) {
  const id = identity(positionId, 'Position ID');
  const position = account.positions.find(p => p.id === id);
  if (!position) fail('POSITION_NOT_FOUND', 'This practice position is no longer open.');
  return position;
}

export function estimatePositionExit(position, { bid, fee = 0, quantity } = {}) {
  const count = quantity === undefined ? position.quantity : quantityValue(quantity);
  if (count > position.quantity) fail('INVALID_QUANTITY', 'You cannot close more contracts than you hold.');
  const bidUnits = priceUnits(bid, 'Bid price', true);
  const feeUnits = toMoneyUnits(fee, 'Total exit fee');
  const grossUnits = multiply(bidUnits, count);
  // Allocate gross cost and fee separately; the final close takes any remainder.
  const entryGrossUnits = proportional(position.entryGrossUnits, count, position.quantity);
  const entryFeeUnits = proportional(position.entryFeeUnits, count, position.quantity);
  const costBasisUnits = entryGrossUnits + entryFeeUnits;
  const netProceedsUnits = grossUnits - feeUnits;
  const pnlUnits = safeResult(netProceedsUnits - costBasisUnits);
  return {
    quantity: count, bid: fromMoneyUnits(bidUnits), grossProceeds: fromMoneyUnits(grossUnits),
    fee: fromMoneyUnits(feeUnits), fees: fromMoneyUnits(feeUnits), netProceeds: fromMoneyUnits(netProceedsUnits),
    costBasis: fromMoneyUnits(costBasisUnits), pnl: fromMoneyUnits(pnlUnits),
    returnPct: costBasisUnits ? pnlUnits / costBasisUnits * 100 : null,
    bidUnits, grossUnits, feeUnits, entryGrossUnits, entryFeeUnits, costBasisUnits, netProceedsUnits, pnlUnits,
  };
}

function exitPosition(account, options, type) {
  const transactionId = requireNewTransaction(account, options.transactionId);
  const position = getPosition(account, options.positionId);
  const estimate = estimatePositionExit(position, options);
  if (account.cashUnits + estimate.netProceedsUnits < 0) {
    fail('INSUFFICIENT_FUNDS', 'The available cash and exit proceeds cannot cover the exit fee.');
  }
  const timestamp = timestampValue(options.timestamp);
  const next = clone(account);
  const remaining = next.positions.find(p => p.id === position.id);
  remaining.quantity -= estimate.quantity;
  remaining.entryGrossUnits -= estimate.entryGrossUnits;
  remaining.entryFeeUnits -= estimate.entryFeeUnits;
  remaining.entryCostUnits -= estimate.costBasisUnits;
  remaining.updatedAt = timestamp;
  next.positions = next.positions.filter(p => p.quantity > 0);
  next.cashUnits = safeResult(next.cashUnits + estimate.netProceedsUnits);
  next.realizedPnlUnits = safeResult(next.realizedPnlUnits + estimate.pnlUnits);
  next.totalFeesUnits = safeResult(next.totalFeesUnits + estimate.feeUnits);
  next.transactions.push({
    id: transactionId, type, asset: position.asset, contractId: position.contractId, side: position.side,
    positionId: position.id, quantity: estimate.quantity, priceUnits: estimate.bidUnits,
    grossUnits: estimate.grossUnits, feeUnits: estimate.feeUnits, costBasisUnits: estimate.costBasisUnits,
    netCashChangeUnits: estimate.netProceedsUnits, realizedPnlUnits: estimate.pnlUnits, timestamp,
    ...(type === 'SETTLE' ? { officialWinningSide: options.officialWinningSide } : {}),
  });
  next.transactionIds.push(transactionId);
  return validateAccount(next);
}

export function closePosition(account, options = {}) { return exitPosition(account, options, 'CLOSE'); }

/** Only call after the server has verified an official outcome for this contract. */
export function settlePosition(account, options = {}) {
  validateAccount(account);
  const winner = sideValue(options.officialWinningSide);
  const position = getPosition(account, options.positionId);
  return exitPosition(account, {
    ...options, officialWinningSide: winner, bid: winner === position.side ? 1 : 0, quantity: position.quantity,
  }, 'SETTLE');
}

/** Hypothetical calculator only: no account state is changed. */
export function estimateTrade({ quantity, ask, bid, entryFee = 0, exitFee = 0 } = {}) {
  const count = quantityValue(quantity);
  const askUnits = priceUnits(ask, 'Ask price', false);
  const entryFeeUnits = toMoneyUnits(entryFee, 'Total entry fee');
  const entryGrossUnits = multiply(askUnits, count);
  return estimatePositionExit({
    quantity: count, entryGrossUnits, entryFeeUnits, entryCostUnits: safeResult(entryGrossUnits + entryFeeUnits),
  }, { bid, fee: exitFee });
}

/**
 * marksByPositionId: { [position.id]: { bid: USD, fee?: total liquidation fee } }
 * A scalar bid is also accepted and explicitly assumes a zero exit fee.
 * Missing marks keep full equity/unrealized P&L null rather than manufacturing a value.
 */
export function calculateAccountSummary(account, marksByPositionId = {}) {
  validateAccount(account);
  if (!marksByPositionId || typeof marksByPositionId !== 'object') fail('INVALID_MARKS', 'Position marks must be an object.');
  const missingMarks = [];
  let knownPositionValueUnits = 0;
  let knownUnrealizedPnlUnits = 0;
  let costBasisUnits = 0;
  const positions = account.positions.map(position => {
    costBasisUnits = safeResult(costBasisUnits + position.entryCostUnits);
    const mark = marksByPositionId[position.id];
    let estimate = null;
    if (mark !== undefined && mark !== null) {
      const input = typeof mark === 'object' ? mark : { bid: mark, fee: 0 };
      if ((input.contractId !== undefined && input.contractId !== position.contractId) ||
          (input.asset !== undefined && input.asset !== position.asset) ||
          (input.side !== undefined && input.side !== position.side)) {
        fail('MARK_MISMATCH', 'The quote does not match this practice position.');
      }
      if (input.bid !== undefined && input.bid !== null) {
        estimate = estimatePositionExit(position, input);
        knownPositionValueUnits = safeResult(knownPositionValueUnits + estimate.netProceedsUnits);
        knownUnrealizedPnlUnits = safeResult(knownUnrealizedPnlUnits + estimate.pnlUnits);
      }
    }
    if (!estimate) missingMarks.push(position.id);
    return {
      ...position,
      entryPrice: fromMoneyUnits(position.entryGrossUnits) / position.quantity,
      averageCost: fromMoneyUnits(position.entryCostUnits) / position.quantity,
      costBasis: fromMoneyUnits(position.entryCostUnits), currentBid: estimate ? estimate.bid : null,
      value: estimate ? estimate.netProceeds : null, unrealizedPnl: estimate ? estimate.pnl : null,
      returnPct: estimate ? estimate.returnPct : null,
    };
  });
  const hasCompleteMarks = missingMarks.length === 0;
  return {
    mode: 'PAPER', currency: 'USD', attemptId: account.attemptId, resetCount: account.resetCount,
    initialBalance: STARTING_BALANCE, cash: fromMoneyUnits(account.cashUnits),
    costBasis: fromMoneyUnits(costBasisUnits),
    equity: hasCompleteMarks ? fromMoneyUnits(safeResult(account.cashUnits + knownPositionValueUnits)) : null,
    realizedPnl: fromMoneyUnits(account.realizedPnlUnits),
    unrealizedPnl: hasCompleteMarks ? fromMoneyUnits(knownUnrealizedPnlUnits) : null,
    totalPnl: hasCompleteMarks ? fromMoneyUnits(safeResult(account.realizedPnlUnits + knownUnrealizedPnlUnits)) : null,
    totalFees: fromMoneyUnits(account.totalFeesUnits),
    knownPositionValue: fromMoneyUnits(knownPositionValueUnits),
    positions, missingMarks, hasCompleteMarks, feePolicy: 'explicit-total-fee',
  };
}

export function resetAccount(account, { attemptId } = {}) {
  validateAccount(account);
  const nextId = attemptId === undefined ? `attempt-${account.resetCount + 2}` : identity(attemptId, 'Attempt ID');
  if (nextId === account.attemptId) fail('INVALID_ATTEMPT', 'A reset must start a new practice attempt.');
  const next = createAccount({ userId: account.userId, attemptId: nextId });
  next.resetCount = safeResult(account.resetCount + 1);
  return next;
}
