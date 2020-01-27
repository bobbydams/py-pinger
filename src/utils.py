import configparser
from os import path
from json import dumps, loads
import datetime
from pytz import UTC
from urllib.request import urlopen, Request
import logging


SENTRY_CLIENT = None


def get_logger():
    log = logging.getLogger('pinger')
    hdlr = logging.FileHandler('pinger.log')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    log.setLevel(logging.DEBUG)
    return log


log = get_logger()


def setup_sentry():
    from raven import Client

    global SENTRY_CLIENT
    settings = get_settings()
    if settings.get('sentry'):
        SENTRY_CLIENT = Client(settings['sentry']['url'])


def only_log():
    settings = get_settings()
    if settings['main']['only_log'] == 'true':
        return True
    else:
        return False


def debug_mode():
    settings = get_settings()
    if settings['main']['debug'] == 'true':
        return True
    else:
        return False


def get_now():
    return datetime.datetime.utcnow().replace(tzinfo=UTC)


def sigterm_handler(workers):
    for w in workers:
        w.kill()


def send_messages(message):
    settings = get_settings()
    if settings.get('slack'):
        send_to_slack(message)
    if settings.get('hipchat'):
        send_to_hipchat(message)
    if settings.get('sentry'):
        send_to_sentry(message)
    log.error(message)


def send_to_hipchat(message, color='green', meme='(yey)', notify=True):
    settings = get_settings()
    HIPCHATAUTH = settings['hipchat']['auth']
    HIPCHATROOM = settings['hipchat']['room']
    HIPCHATURL = 'https://api.hipchat.com/v2/room/{}/notification?auth_token={}'.format(
        HIPCHATROOM, HIPCHATAUTH
    )
    if not meme:
        meme = settings['hipchat']['emoji']

    if only_log():
        try:
            req = Request(HIPCHATURL)
            data = {
                "color": color,
                "message": "{} {}".format(message, meme),
                "notify": notify,
                "message_format": "text",
            }
            data = dumps(data)
            req.add_header('Content-Type', 'application/json')
            with urlopen(req, data, timeout=20) as f:
                log.info('---- Notified Hipchat! Message {} ----'.format(message))
        except Exception as e:
            log.error('Error sending to Hipchat!')
            log.exception(e)
    else:
        log.debug(
            '---- DEBUG HipChat! Message {} {} {} {} ----'.format(
                message, meme, color, notify
            )
        )


def send_to_slack(message, meme=':robot:', send_messages=True):
    settings = get_settings()
    SLACKURL = settings['slack']['url']
    SLACKCHANNEL = settings['slack']['channel']
    SLACKTOKEN = settings['slack']['token']
    SLACKUSER = settings['slack']['user']

    if not meme:
        meme = settings['slack']['emoji']

    if only_log():
        try:
            req = Request(SLACKURL)
            req.add_header('Content-Type', 'application/json; charset=utf-8')
            req.data = dumps(
                {
                    'token': SLACKTOKEN,
                    'channel': SLACKCHANNEL,
                    'as_user': True,
                    'icon_emoji': meme,
                    'username': SLACKUSER,
                    'text': message,
                }
            ).encode('utf-8')
            with urlopen(req, timeout=20) as f:
                log.info('---- Notified Slack! {} ----'.format(message))
        except Exception as e:
            log.error('Error sending to Slack!')
            log.exception(e)
    else:
        log.debug('---- DEBUG Slack! Message {} ----'.format(message))


def send_to_sentry(message):
    if not only_log():
        SENTRY_CLIENT.captureMessage('{}'.format(message))


def get_settings(config_file=None):
    config = configparser.ConfigParser()
    if not config_file:
        config_path = path.dirname(path.realpath(__file__))
        config.read(path.join(config_path, '../pinger.ini'))
    else:
        config.read(config_file)
    return dict(config._sections)


def request_token():
    settings = get_settings()
    username = settings['token_auth']['username']
    password = settings['token_auth']['password']
    url = settings['token_auth']['url']

    data = {'email': username, 'password': password}

    req = Request(url, data=dumps(data).encode())
    req.add_header('Content-Type', 'application/json')

    with urlopen(req) as response:
        return loads(response.read())['auth_token']
