
import logging
import sys
from multiprocessing import Process
from configparser import ConfigParser
import lst_poller
import lst_worker


"""
Expected arguments:
    Required:
        - config_fp
        - running mode (debug or normal)
"""
global config_fp, debug_mode, rdb, langs, proj, usr, pssw
config_fp = debug_mode = None # initialize to avoid NameError

logger = logging.getLogger('app')
_h = logging.FileHandler('logs/app.log')
_h.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
logger.addHandler(_h)
logger.setLevel(logging.INFO)
logger.propagate = False


def run():
    logger.info('[RUN] Starting the game')
    set_args()
    load_config()
    logger.info('[RUN] Checked argv and config: OKAY.')
    Process(target=start_poller).start()
    Process(target=start_worker).start()


def set_args():
    """
    Copies command line arguments to global variables.
    Required arguments:
            argv[1] -   config file
            argv[2] -   starting modedebug mode file

    Will terminate if arguments are invalid.
    """
    global config_fp, debug_mode
    # Accept only 3 arguments
    arguments = list(sys.argv[:-1]) if sys.argv[-1] == '&' else list(sys.argv)
    if len(arguments) == 3:
        # first argument is config file
        config_fp = arguments[1]
        # second argument contains starting mode
        if arguments[2] == 'debug':
            debug_mode = True
        else:
            debug_mode = False
    else:
        if len(arguments) < 2:
            logger.warning('[SET_ARGS] Too few arguments [{}]. 3 ' \
            'expected. Terminating.'.format(' '.join(arguments)))
        elif len(arguments) > 3:
            logger.warning('[SET_ARGS] Too many arguments [{}]. 3 ' \
            'expected. Terminating.'.format(' '.join(arguments)))
        sys.exit(2)


def start_poller():
    logger.info('[START_POLLER] Starting poller on [{}] ({})'.format(proj, \
        ', '.join(langs)))
    lst_poller.main(proj, langs, rdb)


def start_worker():
    logger.info('[START_worker] Starting worker in {} mode'.format \
        ('DEBUG' if debug_mode else 'normal'))
    lst_worker.main(rdb, debug_mode, usr, pssw)


def load_config():
    """
    Load from config file:
        proj    -   project to run on service  (string)
        langs   -   list of languages to run on (list of strings)

    Additionally we check that both variables are in the list of supported
    projects and languages (also loaded from config file).

    Will terminate if options are invalid.
    """
    global langs, proj, usr, pssw, rdb
    try:
        config = ConfigParser()
        config.read_file(open(config_fp))
    except:
        logger.warning('[LOAD_CONFIG] Unable to open config [{}]. Terminating' \
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
            usr = config.get('credentials', 'username')
            pssw = config.get('credentials', 'password')
        except:
            logger.warning('[LOAD_CONFIG] Unable to load required data from ' \
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
                logger.warning('[LOAD_CONFIG] Not supported language(s) ({}) ' \
                    'and project [{}]. Terminating'.format(', '.join(not_supported), \
                    proj))
                sys.exit(1)
            # Languages not supported
            elif not_supported:
                logger.warning('[LOAD_CONFIG] Not supported language(s) ' \
                    '({}). Terminating'.format(', '.join(not_supported)))
                sys.exit(1)
            # Project not supported
            elif proj not in supported_projs:
                logger.warning('[LOAD_CONFIG] Not supported project [{}]. ' \
                    'Terminating'.format(proj))
                sys.exit(1)


if __name__ == '__main__':
    run()
