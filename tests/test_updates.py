import json
import queue
from types import SimpleNamespace
import pytest
from codexmeter.updates import UpdateStore, release_key, RELEASES_URL

def release(tag='windows-c6-2026.11.02', **extra):
    return {'tag_name': tag, 'draft': False, 'prerelease': False, **extra}

def test_new_release_and_persistent_notification_deduplication(tmp_path):
    store = UpdateStore(tmp_path / 'updates.json', current='windows-c6-2026.11.01')
    desktop = SimpleNamespace(commands=queue.Queue())
    assert store.check(fetch=release, now=100000)['state'] == 'available'
    assert store.release_url() == RELEASES_URL + '/tag/windows-c6-2026.11.02'
    store.notify_once(desktop)
    assert desktop.commands.get_nowait()[0] == 'update_available'
    UpdateStore(store.path, current='windows-c6-2026.11.01').notify_once(desktop)
    assert desktop.commands.empty()
    store.check(force=True, fetch=lambda: release('windows-c6-2026.11.03'), now=100001)
    store.notify_once(desktop)
    assert desktop.commands.get_nowait()[0] == 'update_available'

@pytest.mark.parametrize('tag', ['windows-c6-2026.10.24', 'windows-c6-2026.11.01'])
def test_old_or_equal_not_an_update(tmp_path, tag):
    store = UpdateStore(tmp_path / 'updates.json', current='windows-c6-2026.11.01')
    assert store.check(fetch=lambda: release(tag))['state'] == 'current'

@pytest.mark.parametrize('data', [release(prerelease=True), release(draft=True), release('v999'),
                                  release('windows-c6-2026.13.01'), {}, []])
def test_unusable_release_is_not_offered(tmp_path, data):
    store = UpdateStore(tmp_path / 'updates.json', current='windows-c6-2026.11.01')
    assert store.check(fetch=lambda: data)['state'] == 'error'
    assert store.release_url() == RELEASES_URL

def test_poll_interval_retry_and_new_installed_baseline(tmp_path):
    store = UpdateStore(tmp_path / 'updates.json', current='windows-c6-2026.11.01')
    calls = []
    def fetch():
        calls.append(1)
        return release()
    store.check(fetch=fetch, now=100000)
    store.check(fetch=fetch, now=100001)
    assert len(calls) == 1
    store.check(force=True, fetch=fetch, now=100002)
    assert len(calls) == 2
    upgraded = UpdateStore(store.path, current='windows-c6-2026.11.02')
    assert upgraded.check(fetch=fetch, now=100003)['state'] == 'current'
    def offline():
        raise OSError('offline')
    assert store.check(force=True, fetch=offline, now=100004)['state'] == 'error'
    store.check(fetch=fetch, now=100005)
    assert len(calls) == 3
    store.check(fetch=fetch, now=103605)
    assert len(calls) == 4

def test_no_releases_corrupt_cache_and_safe_links(tmp_path):
    store = UpdateStore(tmp_path / 'updates.json', current='windows-c6-2026.11.01')
    store.path.write_text('broken')
    assert store.status()['state'] == 'unchecked'
    assert store.check(fetch=lambda: None)['state'] == 'current'
    store.path.write_text(json.dumps({'state': 'available', 'tag': '../../malicious'}))
    assert store.release_url() == RELEASES_URL
    assert release_key('windows-c6-2026.11.01.1') > release_key('windows-c6-2026.11.01')

def test_disabled_survives_restart_and_blocks_requests_and_notifications(tmp_path):
    store = UpdateStore(tmp_path / 'updates.json', current='windows-c6-2026.11.01')
    store.check(fetch=release, now=100000)
    store.set_automatic(False)
    restarted = UpdateStore(store.path, current='windows-c6-2026.11.01')
    def forbidden():
        pytest.fail('Disabled automatic checks must not contact GitHub')
    assert restarted.check(fetch=forbidden, now=200000)['state'] == 'disabled'
    desktop = SimpleNamespace(commands=queue.Queue())
    restarted.notify_once(desktop)
    assert desktop.commands.empty()
    # A user-triggered manual check is allowed but never re-enables background work.
    assert restarted.check(force=True, fetch=release)['state'] == 'available'
    assert not restarted.automatic_enabled()
    restarted.notify_once(desktop)
    assert desktop.commands.empty()
    restarted.set_automatic(True)
    restarted.notify_once(desktop)
    assert desktop.commands.get_nowait()[0] == 'update_available'

def test_disable_during_request_is_not_overwritten(tmp_path):
    store = UpdateStore(tmp_path / 'updates.json', current='windows-c6-2026.11.01')
    def in_flight():
        store.set_automatic(False)
        return release()
    store.check(fetch=in_flight)
    assert not UpdateStore(store.path, current='windows-c6-2026.11.01').automatic_enabled()
    desktop = SimpleNamespace(commands=queue.Queue())
    store.notify_once(desktop)
    assert desktop.commands.empty()

def test_broken_preferences_fail_closed(tmp_path):
    store = UpdateStore(tmp_path / 'updates.json', current='windows-c6-2026.11.01')
    assert store.automatic_enabled()
    store.preferences_path.write_text('broken')
    assert not store.automatic_enabled()
    assert store.check(fetch=lambda: pytest.fail('No network with broken preferences'))['state'] == 'disabled'


def test_default_baseline_does_not_offer_its_own_release(tmp_path):
    from codexmeter.updates import CURRENT_RELEASE
    store = UpdateStore(tmp_path / 'current.json')
    assert store.check(fetch=lambda: release(CURRENT_RELEASE))['state'] == 'current'

def test_release_fetch_uses_repository_identity_and_rejects_redirects(monkeypatch):
    from codexmeter import updates
    from io import BytesIO
    requests = []
    class Response(BytesIO):
        url = 'https://api.github.com/repositories/1432451927/releases/latest'
    def open_response(request, timeout):
        requests.append(request.full_url)
        return Response(json.dumps(release()).encode())
    monkeypatch.setattr(updates.urllib.request, 'urlopen', open_response)
    assert updates.fetch_release()['tag_name'] == release()['tag_name']
    assert requests == [Response.url]
    Response.url = 'https://example.com/releases/latest'
    with pytest.raises(ValueError, match='redirect'):
        updates.fetch_release()
