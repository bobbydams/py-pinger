import pytest
from src import utils


@pytest.fixture
def settings(monkeypatch):
    def mock_return():
        return {
            'main': {
                'only_log': 'true',
                'debug': 'true'
            },
            'slack': {
                'url': 'test',
                'channel': 'test-channel',
                'token': '1234',
                'user': 'bot'
            },
            'hipchat': {
                'auth': '1234',
                'room': 'test-room'
            },
            'sentry': {

            }
        }
    monkeypatch.setattr(utils, 'get_settings', mock_return)
