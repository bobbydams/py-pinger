from src.utils import (send_messages, send_to_slack, send_to_hipchat,
                       debug_mode, only_log)


def test_send_message(settings):
    send_messages('test')


def test_send_to_slack(settings):
    send_to_slack('test message')


def test_send_to_hipchat(settings):
    send_to_hipchat('test message')


def test_debug(settings):
    debug = debug_mode()
    assert debug is True


def test_only_log(settings):
    logging = only_log()
    assert logging is True
