# turkarshreyash@gmail.com * Copyright 2023
#
# Isengard is a tool to run tests on dev vm.
# You much have remote executor ready.
# Can be used to, build brikmock images, run brikmock tests, sync workspace,
# and sync logs.
# 
# Before running any command this module checks is this file is modified.
# If modified, it reloads this module.
# main.py is the entry point of this module. If reload exception is raised,
# main.py reloads this module and runs the last command.
# 


from cmd import Cmd
import os
import pickle
import re
import subprocess
import logging
import sys


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class ReloadException(Exception):
    """
    Module called for reload.
    """
    def __init__(self, line: str = None):
        self.line = line

# Order SIDs
POLARIS_SID = 'cgfzkc-wgp3y66'
CDM_SID = 'gp2zre-jc6kz4i'
BODEGA_POLARIS = ('{\\\\\\"_item_1\\\\\\": {\\\\\\"spark_instance\\\\\\": {'
                    '\\\\\\"context\\\\\\": \\\\\\"dev-155\\\\\\", '
                    '\\\\\\"account\\\\\\": \\\\\\"bodega\\\\\\",'
                    '\\\\\\"dns\\\\\\": \\\\\\"bodega.dev-155.my.rubrik-lab.com'
                    '\\\\\\",'
                    '\\\\\\"username\\\\\\": '
                    '\\\\\\"bodega-test-user@rubrik.com\\\\\\",'
                    '\\\\\\"password\\\\\\": \\\\\\"B0dega!@34\\\\\\", '
                    '\\\\\\"role\\\\\\": '
                    '\\\\\\"00000000-0000-0000-0000-000000000000\\\\\\"}, '
                    '\\\\\\"item_type\\\\\\":'
                    '\\\\\\"polaris_gcp\\\\\\"}}')


REPO='sdmain'
WORKSPACE = f'/Users/Shreyash.Turkar/workspace/{REPO}'
REMOTE_WORKSPACE = f'/home/ubuntu/workspace/{REPO}'

REMOTE_MACHINE = 'ubvm'

REMOTE_LOG_DIR = f'{REMOTE_WORKSPACE}/logs'
LOCAL_LOG_DIR = f'{WORKSPACE}/logs'


LOG_SYNC_CMD = [
    'rsync',
    '-ra',
    f'{REMOTE_MACHINE}:{REMOTE_LOG_DIR}',
    f'{LOCAL_LOG_DIR}/..']

SYNC_WORKSPACE_CMD = [
    'python3',
    f'{WORKSPACE}/tools/remote_executor/remote_executor.py',
    '--push_changes'
]

PULL_WORKSPACE = [
    'python3',
    f'{WORKSPACE}/tools/remote_executor/remote_executor.py',
    '--pull_updates'
]

REMOTE_GEN_DEPS_CMD = "./tools/bzl_tools/build/gen_intellij_deps.sh"

OPEN_LOGS_CMD = [
    'vim',
    f'{LOCAL_LOG_DIR}/latest-run'
]

BUILD_BRICKMOCK_IMAGE_CMD = './src/scripts/brikmock/gen_docker.sh'

DOCKER_SYS_PRUNE_CMD = 'docker system prune'

GET_BRIKMOCK_DOCKER_LATEST_IMAGE_CMD = [
    'ssh',
    '-t',
    'ubvm',
    'docker images -a | sort -k4 -r | grep '
    '\'brikmock\'  | awk \'{print $2}\'  | head -1'
]

GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD = [
    'ssh',
    '-t',
    'ubvm',
    'docker images -a | grep \'brikmock\' |'
    ' awk \'{print $3}\'  | head -1'
]

STOP_BRIKMOCK_CONTAINER_CMD = [
    'ssh',
    '-t',
    'ubvm',
    'docker ps | grep brikmock | awk \'{print $1}\'  | xargs docker stop && '
    'docker rm brikmock'
]

GET_BRIKMOCK_CONTANIER_CMD = [
    'ssh',
    '-t',
    'ubvm',
    'docker ps | grep brikmock'
]

class LocalMachine:

  @staticmethod
  def run_command(
    command: list,
    stdin_str: bytes = None,
    cwd: str = WORKSPACE,
    capture_output: bool = False):

    logging.info(f'Running: {command}\n')

    process = subprocess.run(
      command, cwd=cwd,
      input=stdin_str,
      capture_output=capture_output)

    stdout = process.stdout
    stderr = process.stderr
    logging.info(f'Ran: {command}\nStdout: {stdout}\n')
    if stderr:
        logging.error(f'Ran: {command}\nStderr {stderr}\n')
    if capture_output:
        return str(stdout.decode())
    return ''

class DevMachine:

  @staticmethod
  def __get_cmd_for_sd_dev(command):
    return [
      'ssh',
      '-t',
      'ubvm',
      f'COMPOSE_PROJECT_NAME=home-ubuntu-workspace-{REPO}-master '
      f'{REMOTE_WORKSPACE}/lab/sd_dev_box/sd_dev_box '
      f'--sdmain_repo '
      f'{REMOTE_WORKSPACE} --cache_and_reuse_container '
      f'--exec "source /etc/profile.d/sd_exports.sh && {command}"']

  @staticmethod
  def run_command(
    command: str,
    stdin_str: bytes = None,
    cwd: str = WORKSPACE,
    capture_output: bool = False):

    command_for_remote = DevMachine.__get_cmd_for_sd_dev(command)
    return LocalMachine.run_command(command_for_remote, stdin_str, cwd, capture_output)


def run_and_return(command: str):
    process = subprocess.run(command, capture_output=True)
    return str(process.stdout.decode())


class TestRunner:

  @staticmethod
  def get_cmd_run_test(
    target: str,
    test: str,
    brikmock_image: str = "",
    cp: str = 'polaris',
    real=False):

      command = [
          'DISABLE_DEV_VAULT=1 python3',
          '-m jedi.tools.sdt_runner',
          f'--test_target {target}'
      ]

      bodega_sids = []
      if cp == 'polaris':
          bodega_sids.extend([POLARIS_SID])

      if real:
          bodega_sids.extend([CDM_SID])

      if bodega_sids:
          bodega_sid_str = ','.join(bodega_sids)
          command += [
              '--allow_multiple_byor',
              '--allow_unused_byor ',
              f'--bodega_sid {bodega_sid_str}'
          ]

      if cp == 'polaris':
          command += [
              f'--bodega_fulfilled_items \'{BODEGA_POLARIS}\''
          ]

      command += [
          f'-- --cp {cp}',
          '--use_service_account_client'
        ]

      if not real:
          command += ['--cdm_cluster_model mocked']

          command += [
              '--brikmock_image_name',
              f'{brikmock_image}'
          ]

      if test:
          command += [f' -k {test}']

      return ' '.join(command)

  @staticmethod
  def run_brikmock_test(target: str, test: str, cp: str, brikmock_image: str = None):
    test_cmd = TestRunner.get_cmd_run_test(target, test, brikmock_image, cp)
    return DevMachine.run_command(test_cmd)

  @staticmethod
  def run_test(target: str, test: str):
    test_cmd = TestRunner.get_cmd_run_test(target, test, real=True)
    return DevMachine.run_command(test_cmd)


def maybe_sync_logs(log_sync):
    if not log_sync:
        logging.warning('Skipping log sync')
        return
    logging.info('Syncing logs from remote')
    LocalMachine.run_command(LOG_SYNC_CMD)


def maybe_sync_workspace(sync):
    if not sync:
        logging.warning('Skipping workspace sync')
        return
    logging.info('Syncing local to remote workspace')
    LocalMachine.run_command(SYNC_WORKSPACE_CMD, stdin_str=b'y\ny\n')

def pull_workspace():
    logging.info('Pulling remote to local')
    LocalMachine.run_command(PULL_WORKSPACE)


def get_last_modified_time():
    """Get last modified time of the file."""
    lstat = os.lstat(__file__)
    return lstat.st_mtime


class Config:
    def __init__(self):
        self.target_base = ''
        self.target_file = ''
        self.test = ''
        self.cp = ''
        self.sync = True
        self.log_sync = True
    

class Cache:
    def __init__(self, cache_file):
        self.cache_file = cache_file
    
    def save(self, wal):
        logging.info('Saving cache')
        with open(self.cache_file, 'wb') as file:
            pickle.dump(wal, file)
    
    def reload(self):
        logging.info('Reloading cache')
        try:
            with open(self.cache_file, 'rb') as file:
                return pickle.load(file)
        except FileNotFoundError:
            logging.warning('No cache found.')
            self.save('')
        except Exception as e:
            logging.error(f'Cache corrupted: {e}. Deleting')
            os.unlink(self.cache_file)
        return None



class IsengardShell(Cmd, Cache):
    intro = '\n'\
            f'{bcolors.OKGREEN}' \
            'Welcome to Project: ISENGARD\n' \
            'Producer: turkarshreyash@gmail.com'\
            f'{bcolors.ENDC}' \

    @property
    def target(self):
        return f'{self.config.target_base}:{self.config.target_file}'
    
    @property
    def test(self):
        return self.config.test
    
    @property
    def cp(self):
        return self.config.cp
    
    @property
    def sync(self):
        return self.config.sync
    
    @property
    def log_sync(self):
        return self.config.log_sync

    def __init__(self, cache_file):
        prompt = None
        sync = True
        sync_logs = True

        last_modified = None
        call_for_module_reload = False

        config: Config = Config()

        Cmd.__init__(self)
        Cache.__init__(self, cache_file)

    def save_cache(self):
        self.save(self.config)
    
    def reload_cache(self):
        self.config = self.reload() or Config()

    def check_for_reload(self, line: str):
        logging.info('Checking for reload')
        if get_last_modified_time() != self.last_modified:
            logging.error('File modified. Reloading')
            raise ReloadException(line)

    def precmd(self, line: str) -> str:
        self.check_for_reload(line)
        return line

    def preloop(self) -> None:
        import readline
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        self.reload_cache()
        self.set_prompt()
        readline.parse_and_bind('bind ^I rl_complete')
        readline.set_completer(self.complete)

        self.last_modified = get_last_modified_time()

    def postloop(self) -> None:
        self.save_cache()

    def set_prompt(self):
        self.prompt = f'\n---------------------------------\n' \
                      f'Current target: {self.target}\n' \
                      f'          test: {self.test}\n' \
                      f'            cp: {self.cp}\n' \
                      f'       syncing: {self.sync}\n' \
                      f'   log_syncing: {self.log_sync}\n' \
                      f'\n' \
                      f'{bcolors.OKBLUE}{bcolors.UNDERLINE}isengard>{bcolors.ENDC} '

    def save_cache_and_set_prompt(self):
        """Save cache and set prompt"""
        self.save_cache()
        self.set_prompt()

    def do_set_sync(self, args):
        """
        Set if sync workspace is enabled.
        """
        self.config.sync = args == '1' or args == 'true'
        self.save_cache_and_set_prompt()
    
    def do_set_log_sync(self, args):
        """
        Set if sync logs is enabled.
        """
        self.config.log_sync = args == '1' or args == 'true'
        self.save_cache_and_set_prompt()

    def do_set_target_base(self, args):
        """
        Set target base.
        """
        self.config.target_base = args
        self.save_cache_and_set_prompt()

    def do_set_target(self, args):
        """Set a target test file"""
        self.config.target_file = args
        self.save_cache_and_set_prompt()

    def do_set_test(self, args):
        """Set a target test."""
        self.config.test = args
        self.save_cache_and_set_prompt()

    def do_set_cp(self, args):
        """Set a cp."""
        self.config.cp = args
        self.save_cache_and_set_prompt()

    def do_run_brikmock_test(self, args):
        """Test run"""
        maybe_sync_workspace(self.sync)
        logging.info(f'args: {args}')
        if args:
            brikmock_image = args
        else:
            brikmock_image = LocalMachine.run_command(GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD, capture_output=True)[:-2]
        
        TestRunner.run_brikmock_test(self.target, self.test, self.cp, brikmock_image)
        maybe_sync_logs(self.log_sync)
        
    def do_show_brikmock_command(self, args):
        """"""
        logging.info(f'args: {args}')
        if args:
            brikmock_image = args
        else:
            brikmock_image = LocalMachine.run_command(GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD, capture_output=True)[:-2]

        command = TestRunner.get_cmd_run_test(self.target, self.test, self.cp, brikmock_image)
        logging.info(f'Shreyash {command}')

    def do_run_test(self, _args):
        """Test real"""
        maybe_sync_workspace(self.sync)
        command = TestRunner.run_test(self.target, self.test)
        maybe_sync_logs(self.log_sync)

    def do_sync_workspace(self, _args):
        """Sync local workspace to remote"""
        maybe_sync_workspace(sync=True)

    def do_sync_logs(self, _args):
        """Sync logs from remote"""
        maybe_sync_logs(self.log_sync)

    def do_open_logs(self, _args):
        """Opens the latest logs in new terminal"""
        LocalMachine.run_command(OPEN_LOGS_CMD)

    def do_gen_intellij_deps(self, _args):
        """Generate intellij deps."""
        maybe_sync_workspace(self.sync)
        logging.info('Generate Intellij Deps')
        DevMachine.run_command(REMOTE_GEN_DEPS_CMD, stdin_str=b'y\ny\n')
        pull_workspace()

    def do_make_brikmock3_sdk_internal(self, _args):
        """
        """
        maybe_sync_workspace(self.sync)
        DevMachine.run_command(
            'cd '
            'polaris/src/rubrik/sdk_internal/brikmock3'
            ' && sudo make')
        pull_workspace()

    def do_build_image(self, _args):
        """Build custom brickmock docker."""
        maybe_sync_workspace(self.sync)
        logging.info('Building custom brikmock image.')
        DevMachine.run_command(BUILD_BRICKMOCK_IMAGE_CMD)

    def do_start_brikmock(self, _args):
        """"""
        logging.info('Starting brikmock container on latest build')
        image_id = LocalMachine.run_command(GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD, capture_output=True)[:-2]
        logging.info(f'Brikmock image id: {image_id}')
        command = [
            'ssh',
            '-t',
            'ubvm',
            f'docker run -p 443:443 -p 9999:9999 --name brikmock -d {image_id}'
        ]
        LocalMachine.run_command(command)
        self.do_get_brikmock(None)

    def do_stop_brikmock(self, _args):
        """Stop all brikmock containers"""
        logging.info('Stopping docker container')
        LocalMachine.run_command(STOP_BRIKMOCK_CONTAINER_CMD)

    def do_get_brikmock(self, _args):
        """"""
        logging.info('Getting docker container')
        stdout = LocalMachine.run_command(GET_BRIKMOCK_CONTANIER_CMD, capture_output=True)

        try:
            a = re.findall('0.0.0.0:[0-9]+->443', stdout)[0].split('->')[
                0].split(':')[1]
            b = re.findall('0.0.0.0:[0-9]+->9999', stdout)[0].split('->')[
                0].split(':')[1]
            c = stdout.split()[0]
            logging.info(f'Container {c}, port: {a}, grpc port: {b}')
        except Exception as e:
            logging.error(f'Error finding port. Result: {stdout}')

    def do_reload(self, _):
        """Reloads current module"""
        logging.warning('Called for module reload')
        raise ReloadException()

    def do_ubvm_docker_sys_prune(self, _args):
        """Remove old images and images that are unused by docker system
        prune."""
        logging.info('Running docker system prune inside dev vm.')
        stdout = DevMachine.run_command(DOCKER_SYS_PRUNE_CMD, capture_output=True)
        run(str(stdout).strip())

    def do_exit(self, _):
        """Exit"""
        logging.info('Terminating gracefully.')
        return True

    def do_dummy(self, _):
        """Dummy command"""
        logging.info('Invoked dummy command')
        brikmock_image = LocalMachine.run_command(GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD, capture_output=True)[:-2]
        print('Hello: %s' % brikmock_image)

    def do_ssh_ubvm(self, _):
        """SSH to UBVM"""
        LocalMachine.run_command(['ssh', 'ubvm'])

    def do_set_brikmock_id(self, _):
        """Set brikmock id to run test with"""
        pass


def parse(arg):
    return tuple(map(int, arg.split()))
