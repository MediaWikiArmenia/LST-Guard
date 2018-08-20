
import logging
import sys
from multiprocessing import Process
from configparser import ConfigParser
import lst_poller
import lst_repairer


"""
Expected arguments:
    Required:
        - config_fp
    Optional:
        - debug_mode_fp
"""
global langs, proj, config_fp, dbg_fp, rdb
config_fp = dbg_fp = None # initialize to avoid NameError

logging.basicConfig(
            filename='logs/app.log',
            level=logging.INFO,
            format='%(asctime)s:%(levelname)s:%(message)s')


def run():
    set_args()
    load_config()
    logging.info('[RUN] Checked argv and config: OKAY.')
    Process(target=start_poller).start()
    Process(target=start_repairer).start()


def set_args():
    """
    Copies command line arguments to global variables.
    Accepted arguments:
        Required:
            argv[1] -   config file
        Optional:
            argv[2] -   debug mode file

    Will terminate if arguments are invalid.
    """
    global config_fp, dbg_fp
    # Allow only 1 or 2 arguments
    if len(sys.argv) == 2 or len(sys.argv) == 3:
        # first argument is config file
        config_fp = sys.argv[1]
        # second argument (optional) is debug mode file
        if len(sys.argv) == 3:
            dbg_fp = sys.argv[2]
    else:
        if len(sys.argv) < 2:
            logging.warning('[SET_ARGS] Too few arguments [{}]. 2 or 3 ' \
            'expected. Terminating.'.format(' '.join(sys.argv)))
        elif len(sys.argv) > 3:
            logging.warning('[SET_ARGS] Too many arguments [{}]. 2 or 3 ' \
            'expected. Terminating.'.format(' '.join(sys.argv)))
        sys.exit(2)


def start_poller():
    logging.info('[START_POLLER] Starting poller on [{}] ({})'.format(proj, \
        ', '.join(langs)))
    lst_poller.run(proj, langs, rdb)


def start_repairer():
    logging.info('[START_REPAIRER] Starting repairer in {} mode'.format \
        ('DEBUG' if dbg_fp else 'normal'))
    lst_repairer.run(dbg_fp, rdb)


def load_config():
    """
    Load from config file:
        proj    -   project to run on service  (string)
        langs   -   list of languages to run on (list of strings)

    Additionally we check that both variables are in the list of supported
    projects and languages (also loaded from config file).

    Will terminate if options are invalid.
    """
    global langs, proj, rdb
    try:
        config = ConfigParser()
        config.read_file(open(config_fp))
    except:
        logging.warning('[LOAD_CONFIG] Unable to open config [{}]. Terminating' \
            .format(config_fp))
        sys.exit(1)
    else:
        # Try to load necessary data
        try:
            langs = config.get('run on', 'languages').split()
            proj = config.get('run on', 'project')
            supported_langs = config.get('supported', 'languages').split()
            supported_projs = config.get('supported', 'projects')
            host = config.get('redis database', 'host')
            port = config.get('redis database', 'port')
            id = config.get('redis database', 'db')
            rdb = (host, port, id)
        except:
            logging.warning('[LOAD_CONFIG] Unable to load required data from ' \
                'config [{}]. Terminating'.format(config_fp))
            sys.exit(1)
        else:
        # Check if all selected languages are supported
            not_supported = []
            for lang in langs:
                if lang not in supported_langs:
                    not_supported.append(lang)
            # Both project and languages not supported
            if not_supported and proj not in supported_projs:
                logging.warning('[LOAD_CONFIG] Not supported language(s) ({}) ' \
                    'and project [{}]. Terminating'.format(', '.join(not_supported), \
                    proj))
                sys.exit(1)
            # Languages not supported
            elif not_supported:
                logging.warning('[LOAD_CONFIG] Not supported language(s) ' \
                    '({}). Terminating'.format(', '.join(not_supported)))
                sys.exit(1)
            # Project not supported
            elif proj not in supported_projs:
                logging.warning('[LOAD_CONFIG] Not supported project [{}]. ' \
                    'Terminating'.format(proj))
                sys.exit(1)


if __name__ == '__main__':
    run()
