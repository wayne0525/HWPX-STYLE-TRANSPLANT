import io
import json
from urllib.error import HTTPError
from unittest.mock import patch

from solar.client import suggest

FIELDS = [{'fieldId': 'f1', 'label': 'name'}]
BLOCKS = [{'blockId': 'b1', 'text': 'name: example'}]


def response():
    return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
        'content': json.dumps({'suggestions': [{'fieldId': 'f1', 'value': 'example'}]})}}]}).encode())


def test_slow_request_budget_and_transient_retry():
    with patch.dict('os.environ', {'UPSTAGE_API_KEY': 'test'}), patch(
        'solar.client.urlopen', side_effect=[TimeoutError(), response()]
    ) as call, patch('solar.client.time.sleep'):
        proposals, warnings = suggest(FIELDS, BLOCKS)
    assert len(proposals) == 1
    assert call.call_count == 2
    assert 15 < call.call_args_list[0].kwargs['timeout'] <= 30
    assert not warnings


def test_auth_failure_not_retried_or_leaked():
    with patch.dict('os.environ', {'UPSTAGE_API_KEY': 'secret'}), patch(
        'solar.client.urlopen', side_effect=HTTPError('url', 401, 'secret', {}, None)
    ) as call:
        proposals, warnings = suggest(FIELDS, BLOCKS)
    assert not proposals and call.call_count == 1
    assert 'HTTP_401' in warnings[0] and 'secret' not in warnings[0]


def test_truncated_response_distinguished():
    raw = io.BytesIO(json.dumps({'choices': [{'finish_reason': 'length', 'message': {'content': '{'}}]}).encode())
    with patch.dict('os.environ', {'UPSTAGE_API_KEY': 'test'}), patch('solar.client.urlopen', return_value=raw):
        _, warnings = suggest(FIELDS, BLOCKS)
    assert 'RESPONSE_TRUNCATED' in warnings[0]


def test_rate_limit_retries_within_budget():
    with patch.dict('os.environ', {'UPSTAGE_API_KEY': 'test'}), patch(
        'solar.client.urlopen', side_effect=[HTTPError('url', 429, '', {'Retry-After': '2'}, None), response()]
    ), patch('solar.client.time.sleep') as sleep:
        proposals, warnings = suggest(FIELDS, BLOCKS)
    assert len(proposals) == 1 and not warnings
    sleep.assert_called_once_with(2)


def test_invalid_json_does_not_retry():
    with patch.dict('os.environ', {'UPSTAGE_API_KEY': 'test'}), patch(
        'solar.client.urlopen', return_value=io.BytesIO(b'invalid')
    ) as call:
        proposals, warnings = suggest(FIELDS, BLOCKS)
    assert not proposals and call.call_count == 1
    assert 'RESPONSE_INVALID' in warnings[0]


def test_retry_after_exceeding_budget_not_retried():
    with patch.dict('os.environ', {'UPSTAGE_API_KEY': 'test'}), patch(
        'solar.client.urlopen', side_effect=HTTPError('url', 429, '', {'Retry-After': '120'}, None)
    ) as call, patch('solar.client.time.sleep') as sleep:
        _, warnings = suggest(FIELDS, BLOCKS)
    assert call.call_count == 1 and not sleep.called
    assert 'HTTP_429' in warnings[0]
