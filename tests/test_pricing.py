import datetime as dt
import json
from decimal import Decimal

import pytest

from codexmeter.pricing import PricingStore, parse_prices, fingerprint
from codexmeter.local_usage import LocalTokenUsageReader
from codexmeter.payloads import build_usage_payload
from codexmeter.limits import UsageSnapshot

NOW = dt.datetime(2026, 10, 29, 12, tzinfo=dt.timezone.utc)
SOURCE = '''# Pricing
### Standard pricing data
| Model | Short context input | Short context output | Short context cached input | Short context 30m write | Short context 12h write | Long context input | Long context output | Long context cached input | Long context 30m write | Long context 12h write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-6-astra | $10.00 | $50.00 | $1.00 | $12.50 | $25.00 | $20.00 | $75.00 | $2.00 | $25.00 | $50.00 |
| gpt-6.1-sol | $2.00 | $10.00 | $0.10 | $2.50 | $5.00 | $4.00 | $15.00 | $0.20 | $5.00 | $10.00 |
### Batch pricing data
Short context: ≤272K input tokens. Long context: >272K input tokens.
'''


def test_official_parser_and_terms_fail_closed():
    rates = parse_prices(SOURCE)
    assert rates['gpt-6.1-sol']['short'] == ['2.00', '0.10', '10.00']
    assert rates['gpt-6-astra']['long'] == ['20.00', '2.00', '75.00']
    with pytest.raises(ValueError):
        parse_prices(SOURCE.replace('272K', '300K'))
    with pytest.raises(ValueError):
        parse_prices('<html>Access denied</html>')
    assert fingerprint(SOURCE) == fingerprint(SOURCE.replace('\n', '\r\n\n'))


def test_review_preserves_history_and_failed_check_preserves_rates(tmp_path):
    store = PricingStore(tmp_path)
    before = store.revisions()
    state = store.check(fetch=lambda: SOURCE, now=NOW)
    assert state['state'] == 'changed'
    assert store.revisions() == before
    accepted = store.accept_pending(state['source_sha256'], now=NOW)
    assert store.revisions()[-1] == accepted
    assert store.check(force=True, fetch=lambda: SOURCE, now=NOW)['state'] == 'current'
    def fail():
        raise OSError('offline')
    assert store.check(force=True, fetch=fail, now=NOW)['state'] == 'error'
    assert store.revisions()[-1] == accepted
    changed = store.check(force=True, fetch=lambda: SOURCE + '\nPricing terms changed.', now=NOW)
    assert changed['state'] == 'changed'
    with pytest.raises(ValueError):
        store.accept_pending('wrong hash', now=NOW)


def test_cost_model_context_and_unknowns(tmp_path):
    store = PricingStore(tmp_path)
    record = {'time': NOW, 'model': 'gpt-6.1-sol', 'input': 1000, 'tokens': [200, 800, 10]}
    assert store.cost(record)[0] == [Decimal(400), Decimal(80), Decimal(100)]
    long = {**record, 'input': 300000, 'tokens': [100000, 200000, 1000]}
    assert store.cost(long)[0] == [Decimal(400000), Decimal(40000), Decimal(15000)]
    assert store.cost({**record, 'model': 'codex-auto-review'})[0] is None
    assert store.cost({**record, 'cache_write': 200})[0] is None
    assert store.cost({**record, 'time': NOW - dt.timedelta(days=2)})[0] is None
    # A new accepted revision only prices subsequent requests.
    newer = {'effective_from': (NOW + dt.timedelta(hours=1)).isoformat(), 'prices': {'gpt-6.1-sol': {'short': ['20', '1', '100']}}}
    revisions = store.revisions() + [newer]
    assert store.cost(record, revisions)[0][0] == 400
    assert store.cost({**record, 'time': NOW + dt.timedelta(hours=2)}, revisions)[0][0] == 4000


def test_notice_compares_history_without_accepting(tmp_path):
    store = PricingStore(tmp_path)
    state = store.check(fetch=lambda: SOURCE, now=NOW)
    store.accept_pending(state['source_sha256'], now=NOW)
    store.check(force=True, fetch=lambda: SOURCE + '\nTerms changed.', now=NOW)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    summary = store.review_summary()
    assert 'does not necessarily mean' in summary
    assert 'No tracked Standard token rates differ' in summary
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    store.check(force=True, fetch=lambda: SOURCE.replace('$10.00', '$11.00'), now=NOW)
    assert 'gpt-6.1-sol' in store.review_summary()
    store.accept_pending(store.status()['source_sha256'], now=NOW + dt.timedelta(hours=1))
    assert 'No review is pending' in store.review_summary()
    def offline():
        raise OSError('offline')
    store.check(force=True, fetch=offline, now=NOW)
    assert 'does not establish that prices changed' in store.review_summary()


def test_breakdown_joins_turns_deduplicates_and_marks_unknown(tmp_path):
    sessions = tmp_path / 'sessions'
    sessions.mkdir()
    def context(turn, model):
        return {'type': 'turn_context', 'payload': {'turn_id': turn, 'model': model}}
    def usage(response, turn, cached=800):
        return {'type': 'token_usage_record', 'timestamp': NOW.isoformat(), 'payload': {
            'response_id': response, 'turn_id': turn, 'usage': {'input_tokens': 1000, 'cached_input_tokens': cached,
                'output_tokens': 10, 'reasoning_output_tokens': 5, 'total_tokens': 1010}}}
    rows = [context('a', 'gpt-6.1-sol'), usage('one', 'a'), context('b', 'gpt-6-astra'), usage('two', 'b'), usage('three', 'unknown')]
    for name in ('a.jsonl', 'fork.jsonl'):
        path = sessions / name
        path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
        import os
        os.utime(path, (NOW.timestamp(), NOW.timestamp()))
    reader = LocalTokenUsageReader(tmp_path)
    daily = reader.read_daily_tokens(NOW)
    detail = reader.read_breakdown(daily, PricingStore(tmp_path / 'prices'))
    today = detail['today']
    assert today['tokens'] == [600, 2400, 30]
    assert today['total_tokens'] == 3030
    assert today['cost_micro_usd'] == [2400, 880, 600]
    assert today['unpriced_tokens'] == 1010
    assert today['unknown_tokens'] == 0
    assert 'Unknown model' in today['models']
    snapshot = UsageSnapshot('codex', None, None, 90, 123, 'ok', 456, 3030, 3030, detail)
    payload = build_usage_payload(snapshot)
    assert payload.data['b0'][:3] == [600, 2400, 30]
    assert payload.data['b0'][6:] == [1, 0]
    assert len(payload.to_json_bytes()) <= 512


def test_ble_large_totals_remain_within_budget():
    part = {'tokens': [10**12]*3, 'cost_micro_usd': [10**14]*3, 'unpriced_tokens': 1, 'unknown_tokens': 1}
    snapshot = UsageSnapshot('codex', 100, 1800000000, 100, 1800000000, 'ok', 1800000000,
                             3*10**12, 3*10**12, {'today': part, 'week': part})
    assert len(build_usage_payload(snapshot).to_json_bytes()) <= 512
