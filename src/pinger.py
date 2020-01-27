#!/usr/bin/env python
from time import sleep
import datetime
from pytz import UTC
from dateutil import parser
from urllib.error import HTTPError, URLError
from socket import error as SocketError
from json import loads
from urllib.request import urlopen, Request
import signal
import os

from utils import (
    get_settings,
    get_now,
    debug_mode,
    sigterm_handler,
    send_messages,
    get_logger,
    setup_sentry,
    request_token,
)


from flask import Flask, jsonify
import gevent
import gevent.monkey

gevent.monkey.patch_all()

log = get_logger()

STATS = {}


def worker(url):
    global STATS
    settings = get_settings()
    DEBUG = debug_mode()
    INTERVAL = int(settings['main']['interval'])
    ERRINTERVAL = int(settings['main']['error_interval'])

    while 1:
        # Create a stats dict per url
        create_stats_per_url(url)
        try:
            req = Request(url)
            # Set an auth token header if necessary
            set_token_auth(req)

            # Begin checking the endpoints
            with urlopen(req) as fp:
                now = get_now()
                sleeping = False
                status = None
                status_date = None
                message = ''
                line = fp.read()
                if DEBUG:
                    log.debug(
                        '{}: Received response from {}: {}'.format(now, url, line)
                    )
                try:
                    status = loads(line)
                except Exception as e:
                    send_messages(
                        'Error: Could not parse response from'
                        ' endpoint {}'.format(url)
                    )
                    update_stats(url, 'error')

                if status:
                    if STATS[url]['status'] == 'sleeping':
                        # Check if it's time to wake up
                        start = STATS[url]['sleep_start']
                        end = STATS[url]['sleep_end']
                        if DEBUG:
                            log.debug('{} <= {} <= {}'.format(start, now, end))
                        if start <= now <= end:
                            log.info('{}: {} is still asleep! zzzzzz'.format(now, url))
                        else:
                            # Wake Up!
                            update_stats(url, 'ok', None, None)
                            STATS[url]['sleep_start'] = None
                            end = STATS[url]['sleep_end'] = None
                            log.info('{}: {} is waking up! (yawn)'.format(now, url))
                    else:
                        # Check if the time falls between the normal
                        # sleep interval
                        sleepy_time = status.get('sleep', [])
                        for sleep in sleepy_time:
                            start = sleep.get('start')
                            end = sleep.get('start')
                            duration = sleep.get('duration')
                            # Check that to and from are parsable dates
                            if start and duration:
                                try:
                                    start = parser.parse(start).replace(tzinfo=UTC)
                                    # The from time is the to time + the duration
                                    # in minutes
                                    end = parser.parse(end).replace(tzinfo=UTC)
                                    end += datetime.timedelta(minutes=duration)
                                    # Does the time now fall between the sleep period?
                                    if DEBUG:
                                        log.debug(
                                            '{} <= {} <= {}'.format(start, now, end)
                                        )
                                        log.info(
                                            'Sleeping: {}'.format(start <= now <= end)
                                        )
                                    if start <= now <= end:
                                        sleeping = True
                                        update_stats(url, 'sleeping', start, end)
                                        log.info(
                                            '{}: {} is asleep! zzzzzz'.format(now, url)
                                        )
                                        break
                                except Exception as e:
                                    log.error('Error parsing sleep time!')

                    if STATS[url]['status'] != 'sleeping':
                        # Check if the last run time falls in between the
                        # acceptable margin
                        frequency = status.get('frequency', 10)
                        server = status.get('server', '')
                        process = status.get('process', '')
                        reason = status.get('reason', '')
                        status_msg = status.get('status', None)
                        margin = datetime.timedelta(minutes=frequency)
                        # Try to parse the date, if this is not possible throw
                        # an exeption and notify
                        try:
                            status_date = parser.parse(status.get('lastrun', None))
                        except Exception as e:
                            update_stats(url, 'error', process=process, server=server)
                            status_date = None
                            send_messages(
                                'Error: Date Parse {} error for endpoint'
                                ' {}'.format(status.get('lastrun', None), url)
                            )
                        if status_date and not (
                            now - margin <= status_date <= now + margin
                        ):
                            # This is a failure due to the age of the last status, report it.
                            # Also report the last known status, for good information.
                            message = (
                                'Error: {}/{} is outside of the acceptable {} '
                                'minute range. Last Run {} UTC with status {}'.format(
                                    process, server, frequency, status_date, status_msg
                                )
                            )
                            update_stats(url, 'error', process=process, server=server)
                            send_messages(message)
                        elif status_date and (
                            now - margin <= status_date <= now + margin
                        ):
                            if status_msg != 'OK':
                                message = (
                                    'Error: Failure reported on process {} running'
                                    ' on {}. Status: {} Error: {}.'.format(
                                        process, server, status_msg, reason
                                    )
                                )
                                update_stats(
                                    url, 'error', process=process, server=server
                                )
                                send_messages(message)
                            else:
                                # Everything is okay, but check if the last check
                                # was a failure
                                if STATS[url]['status'] == 'error':
                                    message = 'Status: {}/{} ({}) is OK again!'.format(
                                        process, server, url
                                    )
                                    send_messages(message)
                                update_stats(url, 'ok', process=process, server=server)
                        else:
                            # Something is wrong if no status_date exists
                            message = 'Error: {}/{} is not configured properly {} '.format(
                                process, server, url
                            )
                            update_stats(url, 'error', process=process, server=server)
                            send_messages(message)

        except HTTPError as e:
            # If we receive an HTML error, report it as an error
            # https://docs.python.org/3/library/urllib.error.html#urllib.error.HTTPError
            log.exception(e)
            send_messages(
                'Warn: HTTP Error: {} - Code {} - {}'.format(url, e.code, e.reason)
            )
            update_stats(url, 'error')
        except URLError as e:
            # If we receive an URL error, report it as an error
            # https://docs.python.org/3/library/urllib.error.html#urllib.error.URLError
            log.exception(e)
            send_messages('Warn: URLError: {} - {}'.format(url, e))
            update_stats(url, 'error')
        except SocketError as e:
            # If we receive a socket error, report it as a warning
            log.exception(e)
            message = 'Warn: Problem retrieving {}. Will try again in a few minutes.'.format(
                url
            )
            send_messages(message)
            update_stats(url, 'error')

        if STATS[url]['status'] == 'error':
            # Use the longer interval so as not to spam people with errors
            log.warning('Sleeping {} for {} seconds'.format(url, ERRINTERVAL))
            gevent.sleep(ERRINTERVAL)
        else:
            if DEBUG:
                log.debug('Sleeping {} for {} seconds'.format(url, INTERVAL))
            # Everything is fine, use the normal interval
            gevent.sleep(INTERVAL)


def set_token_auth(req):
    settings = get_settings()
    if settings.get('token_auth'):
        auth_token = settings['token_auth'].get('token', '')
        if not auth_token and settings['token_auth'].get('url'):
            try:
                auth_token = request_token()
            except Exception as e:
                log.error(e)
        header = settings['token_auth'].get('header')
        req.add_header(header, auth_token)


def create_stats_per_url(url):
    global STATS
    # Store stats per URL
    if not STATS.get(url):
        STATS[url] = {
            'pings': 0,
            'errors': 0,
            'status': '',
            'sleep_start': None,
            'sleep_end': None,
            'server': None,
            'process': None,
        }
    log.info('{}: Pinging {}'.format(datetime.datetime.utcnow(), url))
    STATS[url]['pings'] = STATS[url]['pings'] + 1


def update_stats(url='', status='', start=None, end=None, process=None, server=None):
    global STATS
    if status == 'error':
        STATS[url]['status'] = 'error'
        STATS[url]['errors'] = STATS[url]['errors'] + 1
        STATS[url]['sleep_start'] = None
        STATS[url]['sleep_end'] = None
    elif status == 'ok':
        STATS[url]['status'] = 'ok'
        STATS[url]['sleep_start'] = None
        STATS[url]['sleep_end'] = None
    elif status == 'sleeping':
        STATS[url]['status'] = 'sleeping'
        STATS[url]['sleep_start'] = start
        STATS[url]['sleep_end'] = end

    STATS[url]['process'] = process
    STATS[url]['server'] = server


def main():
    global SENTRY_CLIENT
    log.info('---- Starting Pinger ----')
    # Read in settings
    try:
        settings = get_settings()
    except Exception as e:
        log.error('Could not read settings! {}'.format(e))

    # Set basic variables
    DEBUG = debug_mode()

    # Get URLs to monitor depending on if we are in DEBUG mode or not
    if DEBUG:
        urls = settings['urls']['dev'].split(',')
    else:
        urls = settings['urls']['prod'].split(',')
    log.info('---- Monitoring {} URLs ----'.format(len(urls)))

    # Setup external alerting configurations
    if settings.get('hipchat'):
        log.info('---- Hip Chat configured! ----')

    if settings.get('slack'):
        log.info('---- Slack configured! ----')

    # Setup Sentry Monitoring
    setup_sentry()

    log.info('---- DEBUGGING {} ----'.format(DEBUG))

    message = '{}\n Monitoring: {}\n'.format('\n'.join(urls), settings['main']['debug'])
    send_messages(message)

    # Start a small Flask webserver to gather results of the checks
    app = Flask(__name__)

    def make_flask_thread():
        def on_exception():
            log.error('---- Flask service crashed! ----')
            # Sleep, maybe the problem will be resolved in 60 seconds?!
            sleep(60)
            log.info('---- Restarting Flask service! ----')
            make_flask_thread()

        log.info('---- Attempting to start Flask service! ----')
        webapp = gevent.spawn(app.run, host='0.0.0.0', port=3002, debug=False)
        webapp.link_exception(on_exception)
        return webapp

    @app.route('/')
    def service_stats():
        tasks = []
        for key, value in STATS.items():
            d = {'url': key}
            for k, v in value.items():
                d[k] = v
            tasks.append(d)
        return jsonify({'data': tasks})

    @app.route('/task/<path:url>')
    def stats_by_url(url):
        data = {}
        status = 200
        if STATS.get(url):
            data = STATS[url]
            if STATS[url].get('status') and STATS[url].get('status') == 'error':
                status = 500
        else:
            status = 404
        return jsonify({'data': data}), status

    make_flask_thread()

    # Make the pinger threads
    workers = []

    # This will allow these greenlets to re-spawn themselves forever!
    def make_thread(key, args):
        def on_exception(thread):
            log.error('Greenlet went BOOM!')
            # Sleep, maybe the problem will be resolved in 60 seconds?!
            sleep(60)
            make_thread(key, args)

        thread = gevent.spawn(worker, args)
        thread.link_exception(on_exception)
        return thread

    workers = [make_thread(worker, u) for u in urls]

    gevent.signal(signal.SIGTERM, sigterm_handler, workers)

    log.info('Terminate me by kill -TERM {}'.format(os.getpid()))

    gevent.wait()

    message = 'Monitoring service shutting down! C-ya later!'
    send_messages(message)

    log.info('---- Exiting Pinger ----')


if __name__ == '__main__':
    main()
