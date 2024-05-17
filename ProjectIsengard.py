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
from typing import Type, List

from paramiko.client import SSHClient, AutoAddPolicy
from paramiko.config import SSHConfig

logging.getLogger(__name__)


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    RED = '\033[91m'
    FAIL = RED
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class ReloadException(Exception):
    """
    Module called for reload.
    """

    def __init__(self, line: str = None):
        self.line = line


class CommandRunException(Exception):
    """
    Command run exception.
    """

    def __init__(self, command: list, stdout: bytes, stderr: bytes):
        self.command = command
        self.stdout = str(stdout.decode())
        self.stderr = str(stderr.decode())


REPO = 'sdmain'
WORKSPACE = f'/Users/Shreyash.Turkar/workspace/{REPO}'
REMOTE_WORKSPACE = f'/home/ubuntu/workspace/{REPO}'

REMOTE_LOG_DIR = f'{REMOTE_WORKSPACE}/logs'
LOCAL_LOG_DIR = f'{WORKSPACE}/logs'


PULL_WORKSPACE = [
    f'{WORKSPACE}/polaris/.buildenv/bin/python',
    f'{WORKSPACE}/tools/remote_executor/remote_executor.py',
    '--pull_updates',
    '--sync_dir_from_remote',
    'src/java/sd/target',
    '--exclude_from_sync',
    'sd-0.1.jar'
]

OPEN_LOGS_CMD = [
    'vim',
    f'{LOCAL_LOG_DIR}/latest-run'
]

BUILD_BRIKMOCK_IMAGE_CMD = './src/scripts/brikmock/gen_docker.sh'

DOCKER_SYS_PRUNE_CMD = 'docker system prune'

GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD = (
    'docker images -a | '
    'grep \'brikmock\' | '
    'awk \'{print $3}\' | '
    'head -1'
)

DELETE_BRIKMOCK_DOCKER_IMAGES = (
    'docker images -a | '
    'grep \'brikmock\' | '
    'awk \'{print $3}\' | '
    'xargs -n1 docker rmi'
)

STOP_BRIKMOCK_CONTAINER_CMD = (
    'docker ps | '
    'grep brikmock | '
    'awk \'{print $1}\' | '
    'xargs docker stop && '
    'docker rm brikmock'
)

GET_BRIKMOCK_CONTAINER_CMD = (
    'docker ps | grep brikmock'
)


class LocalMachine:

    @staticmethod
    def run_command(
        command: list,
        stdin_str: bytes = None,
        cwd: str = WORKSPACE,
        capture_output: bool = False,
        shell: bool = True,
    ):

        if shell:
            command = ' '.join(command)

        logging.info(f'Running: {command}\n')

        process = subprocess.run(
            command, cwd=cwd,
            input=stdin_str,
            capture_output=capture_output,
            shell=shell
        )

        stdout = process.stdout
        stderr = process.stderr
        logging.info(f'Ran: {command}\nStdout: {stdout}\n')
        if stderr and stderr.find(b'Connection to') == -1:
            logging.error(f'Ran: {command}\nStderr {stderr}\n')
            raise CommandRunException(command, stdout, stderr)
        if capture_output:
            return str(stdout.decode())
        return ''


class DevMachine:
    def __init__(self, remote_machine: str, tmux_session: str):
        """
        """
        self.remote_machine = remote_machine
        self.tmux_session = tmux_session
        self.config_file = '/Users/Shreyash.Turkar/.ssh/config'
        self.client: SSHClient = None

    def connect_ssh(self):
        if self.client:
            logging.info('Already connected to ssh')
            return self.client

        logging.info('Connecting to ssh')
        config = SSHConfig()
        config.parse(open(self.config_file))
        host_config = config.lookup(self.remote_machine)
        logging.info(f'Host config: {host_config}')

        client = SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(AutoAddPolicy())
        client.connect(
            hostname=host_config['hostname'],
            username=host_config.get('user'),
            port=int(host_config.get('port', 22)),
            key_filename=host_config['identityfile']
        )

        self.client = client
        logging.info('Connected to ssh')

    def close_ssh(self):
        if not self.client:
            logging.info('No ssh connection to close')
            return
        logging.info('Closing ssh connection')
        self.client.close()
        logging.info('Closed ssh connection')

    def execute_on_tmux(self, command: str):
        logging.info(f'Executing on tmux: {command}')
        stdin, stdout, stderr = self.client.exec_command(
           command=f'tmux send-keys -t {self.tmux_session} '
                   f'\"{command}\" C-m'
        )
        logging.info(f'Executed on tmux: {command}')
        logging.info(f'Stdout: {stdout.read().decode()}')
        logging.info(f'Stderr: {stderr.read().decode()}')

    def execute_sd_dev_box(self, command: str):
        command_on_sd_dev = (
            f'COMPOSE_PROJECT_NAME=home-ubuntu-workspace-{REPO}-master '
            f'{REMOTE_WORKSPACE}/lab/sd_dev_box/sd_dev_box '
            f'--sdmain_repo '
            f'{REMOTE_WORKSPACE} --cache_and_reuse_container '
            f'--exec "source /etc/profile.d/sd_exports.sh && {command}"'
        )
        logging.info(f'Executing on sd dev box: {command_on_sd_dev}')
        self.client.exec_command(command=command_on_sd_dev)

    def execute(self, command: str):
        logging.info(f'Executing: {command}')
        stdin, stdout, stderr = self.client.exec_command(command=command)
        return stdout.read().decode()


class TestRunner:

    @staticmethod
    def sync_bodega_fulfilled_items(
        remote_machine: DevMachine,
        dev: str,
        account: str = 'bodega'
    ):
        import tempfile
        bodega_item = TestRunner.get_bodega_fulfilled_items(
            dev,
            account
        ).encode()
        logging.info('bodega fulfilled items: %s' % bodega_item)
        with tempfile.NamedTemporaryFile(delete=False) as tp:
            tp.write(bodega_item)
            tp.close()
            file_name = tp.name.split('/')[-1]
            remote_file_name = f'{REMOTE_WORKSPACE}/{file_name}'
            logging.info(f'Copying {tp.name} to {remote_file_name}')
            sftp = remote_machine.client.open_sftp()
            sftp.put(tp.name, remote_file_name)
        return remote_file_name

    @staticmethod
    def get_bodega_fulfilled_items(dev: str, account: str):
        return (
            '{"_item_1":'
            '{"spark_instance":{'
            f'"context":"{dev}",'
            f'"account":"{account}",'
            f'"dns":"{account}.{dev}.my.rubrik-lab.com",'
            '"username":"bodega-test-user@rubrik.com",'
            '"password":"B0dega\\\\!@34",'
            '"role":"00000000-0000-0000-0000-000000000000"},'
            '"item_type":"polaris_gcp"'
            '}'
            '}'
        )

    @staticmethod
    def get_cmd_run_test(
        target: str,
        test: str,
        polaris_sid: str,
        bodega_fullfilled_items_file: str = '',
        brikmock_image: str = '',
        cp: str = 'polaris',
        real: bool = True,
        brikmock_instance_id: str = '2fb5879e63a0',
        cdm_sid: str = '',
        other_sids: List[str] = [],
    ):

        command = [
            'DISABLE_DEV_VAULT=1 python3',
            '-m jedi.tools.sdt_runner',
            f'--test_target {target}'
        ]

        bodega_sids = []
        if cp == 'polaris':
            bodega_sids.extend([polaris_sid])

        if real:
            bodega_sids.extend([cdm_sid])
            bodega_sids.extend(other_sids)

        if bodega_sids:
            bodega_sid_str = ','.join(bodega_sids)
            command += [
                '--allow_multiple_byor',
                '--allow_unused_byor',
                f'--bodega_sid {bodega_sid_str}'
            ]

        if cp == 'polaris':
            command += [
                f'--bodega_fulfilled_items '
                f'\'$(echo `cat {bodega_fullfilled_items_file}`)\''
            ]

        command += [
            f'-- --cp {cp}',
            '--use_service_account_client',
            '--reuse-session',
            '--skip-cleanup-session'
        ]

        if not real:
            command += ['--cdm_cluster_model mocked']

            if brikmock_image:
                command += [
                    '--brikmock_image_name',
                    f'{brikmock_image}',
                ]

            if brikmock_instance_id:
                command += [
                    '--brikmock_reuse_instance_id',
                    f'{brikmock_instance_id}'
                ]

        if test:
            command += [f' -k {test}']

        return ' '.join(command)

    @staticmethod
    def run_brikmock_test(
        remote_machine: DevMachine,
        polaris_sid: str,
        dev: str,
        target: str,
        test: str,
        cp: str,
        account: str,
        brikmock_image: str = None,
    ):
        file_name = TestRunner.sync_bodega_fulfilled_items(remote_machine,
                                                           dev, account)
        test_cmd = TestRunner.get_cmd_run_test(
            target=target,
            test=test,
            polaris_sid=polaris_sid,
            bodega_fullfilled_items_file=file_name,
            brikmock_image=brikmock_image,
            cp=cp,
            real=False
        )
        remote_machine.execute_on_tmux(command=test_cmd)
        logging.info(f'Deleting {file_name}')
        remote_machine.execute_on_tmux(command=f'rm -rf {file_name}')

    @staticmethod
    def run_test(
        remote_machine: DevMachine,
        polaris_sid: str,
        dev: str,
        target: str,
        test: str,
        cp: str,
        account: str,
        cdm_sid: str = '8ymwnn-jy7ijv4',
        other_sids: List[str] = ['5wh7hr-ipmo72m'],
    ):
        file_name = TestRunner.sync_bodega_fulfilled_items(remote_machine,
                                                           dev, account)
        test_cmd = TestRunner.get_cmd_run_test(
            target=target,
            test=test,
            polaris_sid=polaris_sid,
            bodega_fullfilled_items_file=file_name,
            cp=cp,
            real=True,
            cdm_sid=cdm_sid,
            other_sids=other_sids,
        )
        remote_machine.execute_on_tmux(command=test_cmd)
        logging.info(f'Deleting {file_name}')
        remote_machine.execute_on_tmux(command=f'rm -rf {file_name}')


def maybe_sync_logs(log_sync, remote_machine):
    if not log_sync:
        logging.warning('Skipping log sync')
        return
    logging.info('Syncing logs from remote')
    log_sync_cmd = [
        'rsync',
        '-ra',
        f'{remote_machine}:{REMOTE_LOG_DIR}',
        f'{LOCAL_LOG_DIR}/..'
    ]
    LocalMachine.run_command(log_sync_cmd)


def maybe_sync_workspace(sync, remote_machine):
    if not sync:
        logging.warning('Skipping workspace sync')
        return
    logging.info('Syncing local to remote workspace')
    cmd = [
        f'{WORKSPACE}/polaris/.buildenv/bin/python',
        f'{WORKSPACE}/tools/remote_executor/remote_executor.py',
        f'--push_changes --remote_name {remote_machine}'
    ]
    LocalMachine.run_command(cmd, stdin_str=b'y\ny\n')


def pull_workspace():
    logging.info('Pulling remote to local')
    LocalMachine.run_command(PULL_WORKSPACE)


def get_last_modified_time():
    """Get last modified time of the file."""
    lstat = os.lstat(__file__)
    return lstat.st_mtime


class Config:
    def __init__(self):
        self.target_base: str = ''
        self.target_file: str = ''
        self.test: str = ''
        self.cp: str = ''
        self.sync: bool = True
        self.log_sync: bool = True
        self.dev: str = ''
        self.remote_machine: str = ''
        self.polaris_sid: str = ''
        self.tmux_session_id: str = ''
        self.use_tmux: bool = False
        self.account: str = ''


class Cache:
    def __init__(self, cache_file, cache_type: Type[object]):
        self.cache_type = cache_type()
        self.cache_file = cache_file

    def save(self, wal: object):
        wal_typed = self.cache_type
        wal_typed.__dict__ = wal.__dict__
        logging.info('Saving cache')
        with open(self.cache_file, 'wb') as file:
            pickle.dump(wal_typed, file)

    def reload(self) -> object:
        logging.info('Reloading cache')
        wal = None
        try:
            with open(self.cache_file, 'rb') as file:
                wal = pickle.load(file)
        except FileNotFoundError:
            logging.warning('No cache found.')
            logging.info('Creating empty cache file')
            with open(self.cache_file, 'wb') as _:
                pass
        except Exception as e:
            logging.error(f'Cache corrupted: {e}. Deleting')
            os.unlink(self.cache_file)
        wal_typed = self.cache_type
        wal_typed.__dict__ = wal.__dict__
        return wal_typed


class IsengardShell(Cmd, Cache):
    intro = '\n' \
            f'{bcolors.OKGREEN}' \
            'Welcome to Project: ISENGARD\n' \
            'Producer: turkarshreyash@gmail.com' \
            f'{bcolors.ENDC}'

    def is_not_used(self):
        """No use"""
        pass

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

    @property
    def dev(self):
        return self.config.dev

    @property
    def remote_machine(self):
        return self.config.remote_machine

    @property
    def polaris_sid(self):
        return self.config.polaris_sid

    @property
    def tmux_session_id(self):
        return self.config.tmux_session_id

    @property
    def account(self):
        return self.config.account

    def __init__(self, cache_file):
        self.last_modified = get_last_modified_time()
        self.prompt = ''
        self.sync_logs = True

        self.last_modified = None
        self.call_for_module_reload = False

        self.config: Config = Config()

        self.dev_machine: DevMachine = None
        self.loc: LocalMachine = LocalMachine()

        Cmd.__init__(self)
        Cache.__init__(self, cache_file, Config)

    def save_cache(self):
        self.save(self.config)

    def reload_cache(self):
        self.config: Config = self.reload() or Config()

    def check_for_reload(self, line: str):
        logging.info('Checking for reload')
        if get_last_modified_time() != self.last_modified:
            logging.error('File modified. Reloading')
            raise ReloadException(line)

    def precmd(self, line: str) -> str:
        self.check_for_reload(line)
        return line

    def del_dev_machine(self):
        if self.dev_machine:
            self.dev_machine.close_ssh()
            del self.dev_machine
            self.dev_machine = None

    def set_or_reset_dev_machine(self):
        self.del_dev_machine()

        if self.remote_machine and self.tmux_session_id:
            self.dev_machine = DevMachine(self.remote_machine,
                                          self.tmux_session_id)
        if self.dev_machine:
            self.dev_machine.connect_ssh()
            resp = self.dev_machine.execute('hostname')
            logging.info(f'Ran hostname cmd on remote: {resp}')

    def preloop(self) -> None:
        import readline
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        self.reload_cache()

        logging.basicConfig()
        logging.getLogger("paramiko").setLevel(logging.WARNING)

        self.set_or_reset_dev_machine()

        self.set_prompt()
        readline.parse_and_bind('bind ^I rl_complete')
        readline.set_completer(self.complete)
        self.last_modified = get_last_modified_time()

    def postloop(self) -> None:
        self.del_dev_machine()
        self.save_cache()

    def __get_test_prompt(self):
        """Get test prompt"""
        test = (
            f'{bcolors.WARNING}All{bcolors.ENDC}'
            if not self.test else self.test
        )
        return (
            '\n-------| Test Controls |---------\n'
            f'Current target: {self.target}\n'
            f'          test: {test}\n'
            f'            cp: {self.cp}\n'
            f'           account: {self.account}\n'
        )

    def __get_resource_prompt(self):
        """Get resource prompt"""
        self.is_not_used()

        session_id = self.config.tmux_session_id
        tmux_session_id_text = (
            f'{bcolors.OKGREEN}{session_id}'
            if session_id else
            f'{bcolors.WARNING} N/A'
        ) + f'{bcolors.ENDC}'

        client_connect_text = (
            f'{bcolors.OKGREEN}CONNECTED'
            if self.dev_machine and self.dev_machine.client else
            f'{bcolors.WARNING}DISCONNECTED'
        ) + f'{bcolors.ENDC}'

        return (
            '\n-------| Resource Controls |---------\n'
            f'           dev: {self.dev}\n'
            f'remote machine: {self.remote_machine}\n'
            f'   polaris sid: {self.polaris_sid}\n'
            f'      tmux sid: {tmux_session_id_text}\n'
            f'   client conn: {client_connect_text}\n'
        )

    def __get_sync_prompt(self):
        """Get sync prompt"""
        sync_text = (
            f"{bcolors.OKGREEN}ON"
            if self.sync else
            f"{bcolors.WARNING}OFF"
        ) + f"{bcolors.ENDC}"

        log_sync_text = (
            f"{bcolors.OKGREEN}ON"
            if self.log_sync else
            f"{bcolors.WARNING}OFF"
        ) + f"{bcolors.ENDC}"

        return (
            '\n-------| Sync Controls |---------\n'
            f'   wks syncing: {sync_text}\n'
            f'   log syncing: {log_sync_text}\n'
        )

    def __get_inventory_prompt(self):
        """"Get inventory prompt"""
        self.is_not_used()
        return ''

    def set_prompt(self):
        """Set prompt"""
        test_prompt = self.__get_test_prompt()
        sync_prompt = self.__get_sync_prompt()
        self.prompt = (
            '\n'
            f'{self.__get_resource_prompt()}'
            f'\n'
            f'{sync_prompt}'
            f'\n'
            f'{test_prompt}'
            f'\n'
            f'{bcolors.OKBLUE}{bcolors.UNDERLINE}isengard>{bcolors.ENDC} '
        )

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

    def do_set_dev(self, args):
        """Set a dev."""
        self.config.dev = args
        self.save_cache_and_set_prompt()

    def do_set_remote_machine(self, args):
        """Set a remote machine."""
        self.config.remote_machine = args
        self.save_cache_and_set_prompt()
        self.set_or_reset_dev_machine()

    def do_set_tmux_session_id(self, args):
        """Set a tmux session id."""
        self.config.tmux_session_id = args
        self.save_cache_and_set_prompt()
        self.set_or_reset_dev_machine()

    def do_set_polaris_sid(self, args):
        """Set a polaris sid."""
        self.config.polaris_sid = args
        self.save_cache_and_set_prompt()

    def do_set_account(self, args):
        """Set an account."""
        self.config.account = args
        self.save_cache_and_set_prompt()

    def do_delete_brikmock_images(self, _args):
        """Delete all brikmock images"""
        self.is_not_used()
        logging.info('Deleting all brikmock images')
        self.dev_machine.execute(DELETE_BRIKMOCK_DOCKER_IMAGES)

    def do_run_brikmock_test(self, args):
        """Test run"""
        maybe_sync_workspace(self.sync, self.remote_machine)
        logging.info(f'args: {args}')
        if args:
            brikmock_image = args
        else:
            brikmock_image = self.dev_machine.execute(
                GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD,
            )[:-2]

        TestRunner.run_brikmock_test(
            remote_machine=self.dev_machine,
            polaris_sid=self.polaris_sid,
            dev=self.dev,
            target=self.target,
            test=self.test,
            cp=self.cp,
            brikmock_image=brikmock_image,
            account=self.account,
        )
        maybe_sync_logs(self.log_sync, self.remote_machine)

    def do_run_test(self, _args):
        """

        :param args:
        :return:
        """
        maybe_sync_workspace(self.sync, self.remote_machine)
        TestRunner.run_test(
            remote_machine=self.dev_machine,
            polaris_sid=self.polaris_sid,
            dev=self.dev,
            target=self.target,
            test=self.test,
            cp=self.cp,
            account=self.account,
        )
        maybe_sync_logs(self.log_sync, self.remote_machine)

    def do_run_brikmock_test_without_image_id(self, _):
        """Test run with no image id, this will fetch image from docker repo."""
        self.is_not_used()
        maybe_sync_workspace(self.sync, self.remote_machine)
        TestRunner.run_brikmock_test(
            remote_machine=self.dev_machine,
            polaris_sid=self.polaris_sid,
            dev=self.dev,
            target=self.target,
            test=self.test,
            cp=self.cp,
            account=self.account,
        )
        maybe_sync_logs(self.log_sync, self.remote_machine)

    def do_show_brikmock_command(self, args):
        """"""
        logging.info(f'args: {args}')
        if args:
            brikmock_image = args
        else:
            brikmock_image = self.dev_machine.execute(
                command=GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD,
            )[:-2]

        command = TestRunner.get_cmd_run_test(
            target=self.target,
            test=self.test,
            polaris_sid=self.polaris_sid,
            bodega_fullfilled_items_file='/tmp/filename',
            brikmock_image=brikmock_image,
            cp=self.cp,
            real=False
        )
        logging.info(f'{command}')

    def do_sync_workspace(self, _args):
        """Sync local workspace to remote"""
        self.is_not_used()
        maybe_sync_workspace(sync=True, remote_machine=self.remote_machine)

    def do_sync_logs(self, _args):
        """Sync logs from remote"""
        maybe_sync_logs(self.log_sync, self.remote_machine)

    def do_open_logs(self, _args):
        """Opens the latest logs in new terminal"""
        self.is_not_used()
        LocalMachine.run_command(OPEN_LOGS_CMD)

    def do_gen_intellij_deps(self, _args):
        """Generate intellij deps."""
        logging.info('Generate Intellij Deps')
        cmd = [
            f'{WORKSPACE}/polaris/.buildenv/bin/python',
            f'{WORKSPACE}/tools/remote_executor/remote_executor.py'
        ]

        if self.sync:
            cmd += ['--push_changes']
        else:
            cmd += ['--remote_exec_verbose']

        cmd += [
            '--sync_dir_from_remote',
            'src/java/sd/target',
            '--exclude_from_sync',
            'sd-0.1.jar',
            '--command',
            '"./tools/bzl_tools/build/gen_intellij_deps.sh "',
            f'--remote_name',
            f'{self.remote_machine}',
        ]

        LocalMachine.run_command(
            command=cmd,
            stdin_str=b'y\ny\n',
            shell=False
        )

    def do_make_brikmock3_sdk_internal(self, _args):
        """
        """
        maybe_sync_workspace(self.sync, self.remote_machine)
        self.dev_machine.execute_on_tmux(
            command=(
                'cd '
                'polaris/src/rubrik/sdk_internal/brikmock3'
                ' && sudo make'
            )
        )
        pull_workspace()

    def do_build_image(self, _args):
        """Build custom brikmock docker."""
        maybe_sync_workspace(self.sync, self.remote_machine)
        logging.info('Building custom brikmock image.')
        self.dev_machine.execute_on_tmux(
            command=BUILD_BRIKMOCK_IMAGE_CMD
        )

    def do_start_brikmock(self, _args):
        """"""
        logging.info('Starting brikmock container on latest build')
        image_id = self.dev_machine.execute(
            command=GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD,
        )[:-2]
        logging.info(f'Brikmock image id: {image_id}')
        command = [
            'ssh',
            '-t',
            f'{self.remote_machine}',
            f'docker run -P --name brikmock -d {image_id}'
        ]
        LocalMachine.run_command(command)
        self.do_get_brikmock(None)

    def do_stop_brikmock(self, _args):
        """Stop all brikmock containers"""
        self.is_not_used()
        logging.info('Stopping docker container')
        self.dev_machine.execute(
            command=STOP_BRIKMOCK_CONTAINER_CMD
        )

    def do_get_brikmock(self, _args):
        """
        Get brikmock container API server and grpc port.
        """
        self.is_not_used()
        logging.info('Getting docker container')
        stdout = self.dev_machine.execute(
            command=GET_BRIKMOCK_CONTAINER_CMD)

        try:
            a = re.findall('0.0.0.0:[0-9]+->443', stdout)[0].split('->')[
                0].split(':')[1]
            b = re.findall('0.0.0.0:[0-9]+->9999', stdout)[0].split('->')[
                0].split(':')[1]
            c = stdout.split()[0]
            logging.info(f'Container {c}, port: {a}, grpc port: {b}')
        except Exception as e:  # pylint: disable=broad-except
            logging.error(f'Error {e} finding port. Result: {stdout}')

    def do_reload(self, _):
        """Reloads current module"""
        self.is_not_used()
        logging.warning('Called for module reload')
        raise ReloadException()

    def do_ubvm_docker_sys_prune(self, _args):
        """Remove old images and images that are unused by docker system
        prune."""
        self.is_not_used()
        logging.info('Running docker system prune inside dev vm.')
        self.dev_machine.execute_sd_dev_box(
            command=DOCKER_SYS_PRUNE_CMD
        )

    def do_exit(self, _):
        """Exit"""
        self.is_not_used()
        logging.info('Terminating gracefully.')
        return True

    def do_dummy(self, _):
        """Dummy command"""
        self.is_not_used()
        logging.info('Invoked dummy command')
        brikmock_image = self.dev_machine.execute(
            command='ls',
        )[:-2]
        print('Hello: %s' % brikmock_image)

    def do_ssh_ubvm(self, _):
        """SSH to UBVM"""
        self.is_not_used()
        LocalMachine.run_command(['ssh', f'{self.remote_machine}'])

    def do_set_brikmock_id(self, _):
        """Set brikmock id to run test with"""
        pass

    def do_cli(self, _):
        """Open local cli"""
        self.is_not_used()
        LocalMachine.run_command(['bash'])

    def do_orders(self, _):
        """Open local cli"""
        self.is_not_used()
        LocalMachine.run_command(['orders'])


def parse(arg):
    return tuple(map(int, arg.split()))
