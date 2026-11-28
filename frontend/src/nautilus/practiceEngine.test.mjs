import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

// CRA treats source .js as ESM without package type=module. A data import lets
// these dependency-free ledger tests run in Node without changing that package.
const source = await readFile(new URL('./practiceEngine.js', import.meta.url), 'utf8');
const engine = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const { createAccount, quotePurchase, buyContracts, closePosition, settlePosition,
  calculateAccountSummary, resetAccount, estimateTrade, toMoneyUnits, practiceTradeHistory } = engine;
const purchase = (account, overrides = {}) => buyContracts(account, {
  transactionId: 'buy-1', asset: 'BTC', contractId: 'BTC-001', side: 'YES', ask: 0.2, budget: 25,
  ...overrides,
});
const hasCode = code => error => error instanceof engine.PracticeError && error.code === code;

test('starts with $100 shared PAPER cash and does not mutate the account', () => {
  const account = createAccount({ userId: 'member-a' });
  const before = JSON.stringify(account);
  const bought = purchase(account);
  assert.equal(account.cashUnits, 100000000);
  assert.equal(bought.cashUnits, 75000000);
  assert.equal(JSON.stringify(account), before);
  assert.deepEqual(purchase(account), bought, 'same inputs are deterministic');
  assert.equal(createAccount({ userId: 'member-b' }).cashUnits, 100000000);
});

test('$25 budget includes fees and supports 5.1-cent ask exactly', () => {
  const account = createAccount();
  const quote = quotePurchase({ account, ask: '0.051', budget: 25, fee: 0.4 });
  assert.equal(quote.quantity, 482);
  assert.equal(quote.totalCost, 24.982);
  assert.equal(quote.remainingCash, 75.018);
  assert.equal(quote.totalCostUnits, 24982000);
  assert.ok(quote.totalCost <= 25);
  assert.equal(toMoneyUnits(0.000001), 1);
  assert.throws(() => toMoneyUnits(0.0000001), hasCode('INVALID_AMOUNT'));
});

test('spread and entry/exit fees produce a real loss even at a higher gross valuation', () => {
  let account = purchase(createAccount(), { quantity: 100, fee: 0.5 });
  const id = account.positions[0].id;
  const marked = calculateAccountSummary(account, { [id]: { bid: 0.18, fee: 0.25 } });
  assert.equal(marked.cash, 79.5);
  assert.equal(marked.equity, 97.25);
  assert.equal(marked.realizedPnl, 0);
  assert.equal(marked.unrealizedPnl, -2.75);
  account = closePosition(account, { transactionId: 'close-1', positionId: id, bid: 0.18, fee: 0.25 });
  const summary = calculateAccountSummary(account);
  assert.equal(summary.cash, 97.25);
  assert.equal(summary.realizedPnl, -2.75);
  assert.equal(summary.totalFees, 0.75);
  assert.equal(summary.equity, summary.cash);
  assert.equal(summary.unrealizedPnl, 0);
  assert.deepEqual(account.positions, []);
});

test('partial closes allocate microdollar remainders without losing cost basis', () => {
  let account = purchase(createAccount(), { ask: 0.1, quantity: 3, fee: 0.01 });
  const id = account.positions[0].id;
  for (let n = 1; n <= 3; n++) {
    account = closePosition(account, { transactionId: `close-${n}`, positionId: id, quantity: 1, bid: 0.11, fee: 0.001 });
  }
  assert.equal(account.cashUnits, 100017000);
  assert.equal(account.realizedPnlUnits, 17000);
  assert.equal(account.transactions.filter(tx => tx.type === 'CLOSE').reduce((n, tx) => n + tx.costBasisUnits, 0), 310000);
  assert.equal(account.totalFeesUnits, 13000);
});

test('five assets share the same $100 bankroll and maintain independent positions', () => {
  let account = createAccount();
  for (const [i, asset] of ['BTC', 'ETH', 'SOL', 'XRP'].entries()) {
    account = purchase(account, { transactionId: `buy-${i}`, asset, contractId: `${asset}-001` });
  }
  assert.equal(account.cashUnits, 0);
  assert.equal(account.positions.length, 4);
  assert.throws(() => purchase(account, { transactionId: 'buy-doge', asset: 'DOGE' }), hasCode('INSUFFICIENT_FUNDS'));
  account = closePosition(account, { transactionId: 'close-btc', positionId: account.positions[0].id, bid: 0.22 });
  account = purchase(account, { transactionId: 'buy-doge', asset: 'DOGE', contractId: 'DOGE-001' });
  assert.equal(account.positions.length, 4);
  assert.equal(account.positions.find(p => p.asset === 'ETH').quantity, 125);
});

test('official winning and losing settlements are explicit and never guessed', () => {
  const bought = purchase(createAccount(), { ask: 0.1 });
  const id = bought.positions[0].id;
  assert.throws(() => settlePosition(bought, { transactionId: 'settle', positionId: id }), hasCode('INVALID_SIDE'));
  const winner = settlePosition(bought, { transactionId: 'settle', positionId: id, officialWinningSide: 'YES' });
  const loser = settlePosition(bought, { transactionId: 'settle', positionId: id, officialWinningSide: 'NO' });
  assert.equal(winner.cashUnits, 325000000);
  assert.equal(winner.realizedPnlUnits, 225000000);
  assert.equal(loser.cashUnits, 75000000);
  assert.equal(loser.realizedPnlUnits, -25000000);
  assert.equal(loser.transactions.at(-1).type, 'SETTLE');
});

test('missing or mismatched quote data is not turned into a fictitious valuation', () => {
  const account = purchase(createAccount());
  const id = account.positions[0].id;
  const missing = calculateAccountSummary(account);
  assert.equal(missing.equity, null);
  assert.equal(missing.unrealizedPnl, null);
  assert.equal(missing.cash, 75);
  assert.deepEqual(missing.missingMarks, [id]);
  assert.throws(() => calculateAccountSummary(account, { [id]: { bid: 0.2, contractId: 'OTHER' } }), hasCode('MARK_MISMATCH'));
  assert.equal(calculateAccountSummary(account, { [id]: 0 }).equity, 75);
});

test('duplicate transactions, invalid input and overspending are rejected', () => {
  const account = purchase(createAccount());
  assert.throws(() => purchase(account), hasCode('DUPLICATE_TRANSACTION'));
  for (const ask of [0, -0.1, 1.001, NaN, Infinity, undefined]) {
    assert.throws(() => purchase(createAccount(), { ask }));
  }
  for (const quantity of [0, -1, 1.5, '1', null]) {
    assert.throws(() => purchase(createAccount(), { quantity }), hasCode('INVALID_QUANTITY'));
  }
  assert.throws(() => purchase(createAccount(), { quantity: 126 }), hasCode('INSUFFICIENT_BUDGET'));
  assert.throws(() => purchase(createAccount(), { fee: -1 }), hasCode('INVALID_AMOUNT'));
  assert.throws(() => closePosition(account, { transactionId: 'close', positionId: account.positions[0].id, bid: 0.2, quantity: 126 }), hasCode('INVALID_QUANTITY'));
  assert.throws(() => calculateAccountSummary({ ...account, cashUnits: account.cashUnits + 1 }), hasCode('INVALID_ACCOUNT'));
});

test('reset starts a new $100 attempt and only resets this practice object', () => {
  const account = purchase(createAccount({ userId: 'member-a' }));
  const untouched = JSON.stringify(account);
  const reset = resetAccount(account, { attemptId: 'fresh-attempt' });
  assert.equal(reset.userId, 'member-a');
  assert.equal(reset.cashUnits, 100000000);
  assert.equal(reset.resetCount, 1);
  assert.equal(reset.realizedPnlUnits, 0);
  assert.deepEqual(reset.positions, []);
  assert.deepEqual(reset.transactions, []);
  assert.equal(JSON.stringify(account), untouched);
  assert.throws(() => resetAccount(account, { attemptId: account.attemptId }), hasCode('INVALID_ATTEMPT'));
});

test('hypothetical calculator includes entry and exit fees in net return', () => {
  const estimate = estimateTrade({ quantity: 100, ask: 0.1, bid: 0.21, entryFee: 0.5, exitFee: 0.5 });
  assert.equal(estimate.netProceeds, 20.5);
  assert.equal(estimate.costBasis, 10.5);
  assert.equal(estimate.pnl, 10);
  assert.ok(Math.abs(estimate.returnPct - 95.23809523809524) < 1e-10);
});

test('JavaScript preview and server Python ledger produce identical state', () => {
  const events = [
    { operation: 'buy', values: { transactionId: 'a', asset: 'BTC', contractId: 'BTC-12', side: 'YES', ask: 0.051, budget: 25, fee: 0.4 } },
    { operation: 'buy', values: { transactionId: 'b', asset: 'BTC', contractId: 'BTC-12', side: 'YES', ask: 0.067, budget: 12, fee: 0.1 } },
    { operation: 'buy', values: { transactionId: 'c', asset: 'SOL', contractId: 'SOL-12', side: 'NO', ask: 0.13, budget: 17.5, fee: 0.27 } },
    { operation: 'close', values: { transactionId: 'd', positionId: 'pos:1:BTC:YES', quantity: 99, bid: 0.081, fee: 0.11 } },
    { operation: 'settle', values: { transactionId: 'e', positionId: 'pos:3:SOL:NO', officialWinningSide: 'YES' } },
  ];
  let account = createAccount({ userId: 'cross-language' });
  for (const { operation, values } of events) {
    account = ({ buy: buyContracts, close: closePosition, settle: settlePosition })[operation](account, values);
  }
  const modulePath = fileURLToPath(new URL('../../../backend/nautilus_practice.py', import.meta.url));
  const python = `import importlib.util,json,sys\nspec=importlib.util.spec_from_file_location('engine',sys.argv[1]); e=importlib.util.module_from_spec(spec); spec.loader.exec_module(e)\na=e.create_account({'userId':'cross-language'})\nfor x in json.load(sys.stdin):\n a={'buy':e.buy_contracts,'close':e.close_position,'settle':e.settle_position}[x['operation']](a,x['values'])\nprint(json.dumps(a))\n`;
  const result = execFileSync('python3', ['-c', python, modulePath], { input: JSON.stringify(events), encoding: 'utf8' });
  assert.deepEqual(JSON.parse(result), account);
});


test('personal history uses all completed trades of the selected asset without mixing bot history or purchases', () => {
  const earlier = {id:'btc-close',asset:'BTC',side:'YES',type:'CLOSE',priceUnits:300000,costBasisUnits:10000000,realizedPnlUnits:5000000,timestamp:'2026-11-27T10:00:00Z'};
  const recent = {id:'btc-settle',asset:'BTC',side:'NO',type:'SETTLE',priceUnits:0,costBasisUnits:2500000,realizedPnlUnits:-2500000,officialWinningSide:'YES'};
  const transactions = [earlier, ...Array.from({length:25}, (_,i)=>({...earlier,id:'sol-'+i,asset:'SOL'})), {...earlier,id:'buy',type:'BUY'}, recent];
  const before = JSON.stringify(transactions);
  const rows = practiceTradeHistory({transactions}, 'BTC');
  assert.deepEqual(rows.map(row=>row.id), ['btc-settle','btc-close']);
  assert.equal(rows[0].returnPct,-100);
  assert.equal(rows[0].exitPrice,0);
  assert.equal(rows[1].returnPct,50);
  assert.equal(rows[1].realizedPnl,5);
  assert.equal(rows[1].costBasis,10);
  assert.equal(rows[1].exitPrice,0.3);
  assert.equal(practiceTradeHistory({transactions}, 'SOL').length,25);
  assert.deepEqual(practiceTradeHistory(null,'BTC'),[]);
  assert.equal(JSON.stringify(transactions),before);
});
test('missing history values remain unknown, including zero cost basis return', () => {
  const rows = practiceTradeHistory({transactions:[{id:'x',asset:'BTC',type:'CLOSE',costBasisUnits:0}]},'BTC');
  assert.equal(rows[0].returnPct,null);
  assert.equal(rows[0].realizedPnl,null);
  assert.equal(rows[0].exitPrice,null);
});
