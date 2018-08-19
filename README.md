# README Py Pinger

## Overview

This package is a monitoring tool which can be used to monitor various task endpoints
via HTTP(S) and report to Sentry, HipChat or Slack when a task is  out of acceptable bounds.
Py Pinger expects a JSON body returned from the task endpoint with certain values  (see below).

## Ini File

To setup the pinger, copy the pinger_template.ini to pinger.ini and adjust the settings to match your
configuration requirements. If you are not using a certain external service such as HipChat, Slack or Sentry, remove these blocks from the configuration. If you prefer not to send notifications to any services, you can set the `only_log` to `true`. This will prevent any messages from being sent externally.

The urls to monitor should be provided in a comma separated list in the `prod` property. For testing, if `debug` is set to true, the `dev` urls will be used instead.

## Authentication

If your backend uses authentication tokens, this can be provided with the `token_auth` settings.

## Web Server

There is a Flask webserver also built in which displays results of the pinger process. This can be used to monitor
tasks to ensure they are still running correctly. By default the Flask server is available at localhost:3002. In production, it's recommended to put this behind a web server such as Nginx.

### localhost:3002/

The root path will provide information on all running tasks

### localhost:3002/task/<url>

The /task path will provide information on a particular URL. If the task is healthy, a HTTP status 200 will be returned by the endpoint. Otherwise, the endpoint will return a 500 internal server error if there is an error reported. It's best to URL encode the URL that you pass to the endpoint.

## Example Task Response

The task endpoint should return the following JSON body in its response

* status - a status message. Should be "ok" or "error"
* reason - optional reason why the task is failed
* lastrun - required UTC date of the last time the task ran
* frequency - the time in minutes that the task should run. Example: 60 if the task should run
once per hour
* sleep - an optional array of objects with a start and duration. Use this if there are set periods
of time that the task is not running.
* process - an optional tag to identify the task
* server - an optional tag to identify which server a process is being executed on

```
{
   "status":"error|ok",
   "reason":"There was an error",
   "lastrun":"2018-06-28T11:37:48Z",
   "frequency":10,
   "sleep":[
      {
         "start":"22:00:00",
         "duration":450
      }
   ],
   "process":"My Process",
   "server":"My Server"
}
```

## Hosting

If hosting on Ubuntu with systemd, a service file is available for convenience.
Place this file at `/etc/systemd/system/py-pinger.service`. Adjust the `ExecStart` to your setup.

## License

MIT
