# README Py Pinger

## Overview

This package is a monitoring tool which can be used to monitor various task endpoints
via HTTP(S) and report to Sentry, HipChat or Slack when a task is out of acceptable bounds.
Py Pinger expects a JSON body returned from the task endpoint with certain values (see below).

## Ini File

To setup the pinger, copy the pinger_template.ini to pinger.ini and adjust the settings to match your
configuration requirements. If you are not using a certain external service such as HipChat, Slack or Sentry, remove these blocks from the configuration. If you prefer not to send notifications to any services, you can set the `only_log` to `true`. This will prevent any messages from being sent externally.

The urls to monitor should be provided in a comma separated list in the `prod` property. For testing, if `debug` is set to true, the `dev` urls will be used instead.

## Authentication

If your backend uses authentication tokens, this can be provided with the `token_auth` settings. Either set the `token` attribute with a static token, or use the `url`, `username` and `password` settings to ask for a user token through your API.

## Web Server

There is a Flask webserver also built in which displays results of the pinger process. This can be used to monitor
tasks to ensure they are still running correctly. By default the Flask server is available at localhost:3002. In production, it's recommended to put this behind a web server such as Nginx.

### localhost:3002/

The root path will provide information on all running tasks

### localhost:3002/task/<url>

The /task path will provide information on a particular URL. If the task is healthy, a HTTP status 200 will be returned by the endpoint. Otherwise, the endpoint will return a 500 internal server error if there is an error reported. It's best to URL encode the URL that you pass to the endpoint.

## Example Task Response

The task endpoint should return the following JSON body in its response

- status - a status message. Should be "ok" or "error"
- reason - optional reason why the task is failed
- lastrun - required UTC date of the last time the task ran
- frequency - the time in minutes that the task should run. Example: 60 if the task should run
  once per hour
- sleep - an optional array of objects with a start and duration. Use this if there are set periods
  of time that the task is not running.
- process - an optional tag to identify the task
- server - an optional tag to identify which server a process is being executed on

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

# Hosting on Debian/Ubuntu

Note: This was written for Debian/Ubuntu, but can probably be adjusted to work with any Linux flavour.

Prerequisites:

- Nginx (Or your favourite web server)
- Letsencrypt (optional if you want to host over HTTPS)

## Installation of py-pinger

Install the py-pinger package in your location of choice. In this example we use a root account to install in the /opt directory.

cd to /opt and clone this repo in that directory.

```
git clone https://github.com/bobbydams/py-pinger.git && cd py-pinger
```

### Ini file configuration

Create a new ini file by copying the template file.

```
cp pinger.ini.template pinger.ini
```

Next, open the `pinger.ini` and adjust to your setup. Below are some example values that can be used. All external Integrations for Slack, Hipchat, and Sentry are optional. The Token Auth is also optional.

```
[main]
# This will log more information and also simulate
# a time when services are sleeping. This will use the dev urls below
debug=false
# Debug the datetime handling
debug_now=false
# If this is true messages are sent to outside notification channels
only_log=true
# Greeting on startup
greeting=Hello World!
# Check Interval in seconds
interval=60
error_interval=480

# Optional Hipchat Integration
[hipchat]
room=
auth=
emoji=(yey)

# Optional Slack Integration
[slack]
url=https://slack.com/api/chat.postMessage
channel=application-status
token=<Insert Slack API Token>
user=My Task Checker Bot
emoji=:robot:

# Optional Hipchat Integration
[sentry]
url=<API URL provided by Sentry>
# Optional token auth if your backend supports that

# Optional auth endpoint
[token_auth]
# The endpoint to authenticate against
username=my-user
password=my-secret-password
url=https://my-backend.com/login
# The header to use when sending the auth token
header=Authorization

[urls]
# Live URLs, when debug is set to false
prod=https://my-backend.com/task1,https://my-backend.com/task2,https://my-backend.com/task3

# URLs for testing, when debug is set to true
dev=
```

Save and close the ini file.

### Install Python Dependencies

Install a Python virtual env in the py-pinger directory. You can do the next step using whichever way you prefer. On Ubuntu/Debian systems you will need to install `python3-venv` to run the steps below.

```
python3 -m venv .env
.env/bin/activate
```

Install the dependencies in `requirements.txt`

```
pip install -r requirements.txt
```

### Startup

At this point you can start the process directly to check that it's setup properly.

```
python src/pinger.py
```

This will serve the pinger from `localhost:3002`. A log file will also be available at `/opt/py-pinger/pinger.log`

To ensure that the service will startup whent the system startups up, continue with the steps below.

## SystemD

If hosting on a recent version of Ubuntu/Debian with Systemd, a service file is available for convenience.
Place this file at `/etc/systemd/system/py-pinger.service`. Adjust the `ExecStart` command to your setup.

```
# Start Service
systemctl start py-pinger.service

# Stop Service
systemctl stop py-pinger.service

# Service Status
systemctl status py-pinger.service
```

## Nginx Installation & Setup

Install Nginx following the Nginx installation guide https://www.nginx.com/resources/wiki/start/topics/tutorials/install/

Add the following block to the `/etc/nginx/sites-enabled/default` configuration file removing the default location.

Update the server_name to the appropriate domain for your server. This is important for using LetsEncrypt.

```
server {

     server_name monitoring.example-domain.com;

     location / {
          proxy_pass       http://localhost:3002;
          proxy_set_header Host      $host;
          proxy_set_header X-Real-IP $remote_addr;
     }
}
```

## LetsEncrypt Installation and Setup

Got to the LetsEncrypt Certbot documenation and follow the guide for Nginx and the version of Ubuntu/Debian you are using. https://certbot.eff.org/

## Finally

Once everything is setup, go to your domain and check that the service is available. The response should look something like below.

```
{
  data: [
   {
     errors: 0,
     pings: 1,
     process: "My Process",
     server: "My Server",
     sleep_end: null,
     sleep_start: null,
     status: "ok",
     url: "https://your-monitored-domain.com/api/ping"
    }
  ]
}
```

## License

MIT
