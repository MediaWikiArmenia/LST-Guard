#!/usr/bin/env python3

import redis
import subprocess
import sys
from time import sleep
from configparser import ConfigParser

global redb, redb_host, redb_port, redb_id, proc_args, config_fp, debug_mode_fp
config_fp = 'config.ini'
debug_mode_fp = 'debug_edits.html'
debug_mode = False
proc_args = ['nohup', 'python3', 'dumb.py', config_fp, '&']


__doc__ = """
LST-Guard manager: start, restart, stop or status the service.

Calls app.py to start the service (lst_poller and lst_repairer) and uses
Redis to send stop signals, get status or check data.

REQUIREMENTS:
    To start the service, a Redis-server must be running and a valid config
    file available.

ARGUMENTS:
    Required (one of):
        -status            Show status of service (see details below)
        -start             Start service
        -stop              Stop service, processes will finilize and stop
        -restart           Restart service, processes will finilize and restart
        -redis             Show is Redis-server is running and available data
        -help              Print this message

    Optional:
        -start -d          Start in dubug mode, no edits will be made,
                           instead edits will be stored in "{}"
        -restart -d        Same as above
        -redis variable    Print content of "variable"

STATUS:
        'Not started'      Service has not been started
        'Starting'         Signal sent to app.py to start service
        'Running'          Process is running
        'Stopping'         Stop signal send to processes
        'Stopped'          Processes finilized and exited successfully

EXAMPLES:
    Start Lst-guard:
    ./lst_manager -start
""".format(debug_mode_fp)


def run():
    global debug_mode
    # Check command line option
    # Print usage and exit if not valid
    run_option = {  '-start':start_lstg,
                    '-stop':stop_lstg,
                    '-restart':restart_lstg,
                    '-status':get_status,
                    '-redis':check_redis
                    }
    if len(sys.argv)<2 or len(sys.argv)>3 or sys.argv[1]=='-help':
        print(__doc__)
        sys.exit(2)
    elif sys.argv[1] not in run_option.keys():
        print('Unrecognized option "{}". Use "-help" for help'.format(sys.argv[1]))
        sys.exit(2)
    elif sys.argv[1] in ('-start','-restart') and len(sys.argv)==3 and sys.argv[2] != '-d':
        print('Unrecognized argument "{}". Use "-help" for help'.format(sys.argv[2]))
        sys.exit(2)
    elif sys.argv[1] in ('-stop','-status','-help') and len(sys.argv)==3:
        print('Unrecognized argument "{}". Use "-help" for help'.format(sys.argv[2]))
        sys.exit(2)
    # Option/arguments are ok, continue
    print('\n## LST-Guard Manager ##\n')
    open_redis()
    if len(sys.argv)==2:
        run_option[sys.argv[1]]()
    else:
        run_option[sys.argv[1]](sys.argv[2])


def open_redis():
    global redb, redb_host, redb_port, redb_id
    redb_host, redb_port, redb_id = check_config()
    try:
        redb = redis.StrictRedis(host=redb_host, port=redb_port, db=redb_id)
        redb.client_list()
    except:
        print('Error: Unable to open Redis DB (host: {}, port: {}, db: {}).' \
            .format(redb_host, redb_port, redb_id))
        print('Is redis-server running or wrong parameters?')
        sys.exit(1)
    else:
        print('Check: Redis DB running OK (host: {}, port: {}, db: {})'.format \
            (redb_host, redb_port, redb_id))


def lock_redis(unlock=False):
    if unlock:
        redb.set('locked', 0)
    else:
        # Check if locked is set
        if not redb.get('locked'):
            redb.set('locked', 0 if unlock else 1)
        elif int(redb.get('locked')):
            print('Waiting for Redb to unlock...', end=' ', flush=True)
            waited = 0
            while (int(redb.get('locked'))):
                sleep(0.01)
                waited += 1
                if waited > 1000: # we waited 10s
                    print('\nError: Unable to lock Redb. Terminating.' \
                    'Check variable "locked".')
                    sys.exit(1)
            print('OK')
        redb.set('locked', 1)


def check_redis(data=None):
    if data:
        if redb.get(data):
            print('Content of "{}":\t"{}"'.format(data, redb.get(data).decode('utf-8')))
        else:
            print('Variable "{}" is not set.'.format(data))
    else:
        if redb.keys():
            print('The following variables have values:\n \'{}\''.format \
                ('\'\n \''.join([k.decode('utf-8') for k in redb.keys()])))
        else:
            print('No variables in Redis database.')


def start_lstg(debug_mode=False):
    print('Flushing Redis database.')
    redb.flushdb()
    if debug_mode == '-d':
        proc_args.insert(4, debug_mode_fp)
    subprocess.Popen(proc_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, \
        stderr=subprocess.PIPE )
    lock_redis()
    redb.set('poller_status', 'starting')
    redb.set('repairer_status', 'starting')
    lock_redis(unlock=True)
    print('Starting LST-guard: lst_poller & lst_repairer initiated.')
    if debug_mode:
        print('Note: lst_repairer runs in debug mode, edits will be saved in:' \
            ' [{}].'.format(debug_mode_fp))


def restart_lstg(debug_mode=False):
    stop_lstg()
    print('Waiting for processes to stop. This might take 5-20 seconds...')
    still_running = True
    while(still_running):
        sleep(2)
        if redb.get('poller_status').decode('utf-8') == 'stopped' \
            and redb.get('repairer_status').decode('utf-8') == 'stopped':
            still_running = False
    print('All processes stopped. Preparing to restart service.')
    start_lstg(debug_mode)


def stop_lstg():
    lock_redis()
    redb.set('poller_status', 'stopping')
    redb.set('repairer_status', 'stopping')
    lock_redis(unlock=True)
    print('Stopping LST-guard: signal sent to lst_poller & lst_repairer.')


def get_status():
    poller = 'Not started' if not redb.get('poller_status') \
        else redb.get('poller_status').decode('utf-8')
    repairer = 'Not started' if not redb.get('repairer_status') \
        else redb.get('repairer_status').decode('utf-8')
    print('\nProcesses:\tStatus:\nlst_poller\t{}\nlst_repairer\t{}\n'.format \
        (poller.upper(),repairer.upper()))
    if repairer == 'running debug mode':
        print('Note: lst_repairer runs in debug mode, edits are saved in [{}].' \
            .format(debug_mode_fp))


def check_config():
    """
    Validate config.ini and return Redis db details that we need.
    """
    missing_fields = {}
    required_fields = { 'run on':           ['project', 'languages'],
                        'supported':        ['projects', 'languages'],
                        'credentials':      ['username', 'password'],
                        'redis database':   ['host', 'port', 'db']
                        }
    config = ConfigParser()
    try:
        config.read_file(open(config_fp))
    except:
        print('Error: config file [{}] not found. Exiting.'.format(config_fp))
        sys.exit(1)
    else:
        for section in required_fields.keys():
            if not config.has_section(section):
                missing_fields[section] = None
            else:
                for option in required_fields[section]:
                    # Check both that the option label and argument are present
                    # Eg. "password = " without the actual password itself will
                    # be noted as missing option
                    if not config.has_option(section, option) or not \
                        config.get(section, option, fallback=False):
                        missing_fields[section] = missing_fields.get(section,[]) + [option]
        if missing_fields:
            print('Error: missing or empty fields in [config.ini]:')
            for section in missing_fields.keys():
                if not missing_fields[section]:
                    print('  [{}] section missing'.format(section))
                else:
                    print('  missing or empty in section [{}]: {}'.format(section, ', '.join(missing_fields[section])))
            print('Exiting')
            sys.exit(1)
        else:
            print('Check: config file [{}]: OK.'.format(config_fp))
            return (config.get('redis database', 'host'), \
                    config.get('redis database', 'port'), \
                    config.get('redis database', 'db'))


if __name__ == '__main__':
    run()
