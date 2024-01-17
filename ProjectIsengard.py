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

SYNC_WORKSPACE_CMD = [
    f'{WORKSPACE}/polaris/.buildenv/bin/python',
    f'{WORKSPACE}/tools/remote_executor/remote_executor.py',
    '--push_changes'
]

PULL_WORKSPACE = [
    f'{WORKSPACE}/polaris/.buildenv/bin/python',
    f'{WORKSPACE}/tools/remote_executor/remote_executor.py',
    '--pull_updates',
    '--sync_dir_from_remote',
    'src/java/sd/target',
    '--exclude_from_sync',
    'sd-0.1.jar'
]

REMOTE_GEN_DEPS_CMD = "./tools/bzl_tools/build/gen_intellij_deps.sh"

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
        capture_output: bool = False
    ):

        logging.info(f'Running: {command}\n')

        process = subprocess.run(
            command, cwd=cwd,
            input=stdin_str,
            capture_output=capture_output)

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

    @staticmethod
    def __get_cmd_for_sd_dev(command: str, remote_machine: str):
        return [
            'ssh',
            '-t',
            f'{remote_machine}',
            f'COMPOSE_PROJECT_NAME=home-ubuntu-workspace-{REPO}-master '
            f'{REMOTE_WORKSPACE}/lab/sd_dev_box/sd_dev_box '
            f'--sdmain_repo '
            f'{REMOTE_WORKSPACE} --cache_and_reuse_container '
            f'--exec "source /etc/profile.d/sd_exports.sh && {command}"']

    @staticmethod
    def run_command_on_sd_dev_box(
        remote_machine: str,
        command: str,
        stdin_str: bytes = None,
        cwd: str = WORKSPACE,
        capture_output: bool = False
    ):
        command_for_remote = DevMachine.__get_cmd_for_sd_dev(
            command, remote_machine)
        return LocalMachine.run_command(command_for_remote, stdin_str, cwd,
                                        capture_output)

    @staticmethod
    def __create_command(command: str, remote_machine: str):
        return [
            'ssh',
            '-t',
            f'{remote_machine}',
            f'{command}'
        ]

    @staticmethod
    def run_command(
        remote_machine: str,
        command: str,
        stdin_str: bytes = None,
        cwd: str = WORKSPACE,
        capture_output: bool = False
    ):
        command_for_remote = DevMachine.__create_command(
            command, remote_machine)
        return LocalMachine.run_command(command_for_remote, stdin_str, cwd,
                                        capture_output)


class TestRunner:

    @staticmethod
    def get_bodega_fulfilled_items(dev: str):
        return (
            '{\\\\\\"_item_1\\\\\\": {\\\\\\"spark_instance\\\\\\": {'
            f'\\\\\\"context\\\\\\": \\\\\\"{dev}\\\\\\", '
            '\\\\\\"account\\\\\\": \\\\\\"bodega\\\\\\",'
            f'\\\\\\"dns\\\\\\": \\\\\\"bodega.{dev}.my.rubrik-lab.com'
            '\\\\\\",'
            '\\\\\\"username\\\\\\": '
            '\\\\\\"bodega-test-user@rubrik.com\\\\\\",'
            '\\\\\\"password\\\\\\": \\\\\\"B0dega!@34\\\\\\", '
            '\\\\\\"role\\\\\\": '
            '\\\\\\"00000000-0000-0000-0000-000000000000\\\\\\"}, '
            '\\\\\\"item_type\\\\\\":'
            '\\\\\\"polaris_gcp\\\\\\"}}'
        )

    @staticmethod
    def get_cmd_run_test(
        target: str,
        test: str,
        polaris_sid: str,
        dev: str = '',
        brikmock_image: str = '',
        cp: str = 'polaris',
        real=False,
    ):

        command = [
            'DISABLE_DEV_VAULT=1 python3',
            '-m jedi.tools.sdt_runner',
            f'--test_target {target}'
        ]

        bodega_sids = []
        if cp == 'polaris':
            bodega_sids.extend([polaris_sid])

        # if real:
            # bodega_sids.extend([CDM_SID])

        if bodega_sids:
            bodega_sid_str = ','.join(bodega_sids)
            command += [
                '--allow_multiple_byor',
                '--allow_unused_byor ',
                f'--bodega_sid {bodega_sid_str}'
            ]

        if cp == 'polaris':
            get_bodega_fulfilled_items = \
                TestRunner.get_bodega_fulfilled_items(dev)
            command += [
                f'--bodega_fulfilled_items \'{get_bodega_fulfilled_items}\''
            ]

        command += [
            f'-- --cp {cp}',
            '--use_service_account_client',
            # '--reuse-session',
            '--skip-cleanup-session'
        ]

        if not real:
            command += ['--cdm_cluster_model mocked']

            if brikmock_image:
                command += [
                    '--brikmock_image_name',
                    f'{brikmock_image}'
                ]

        if test:
            command += [f' -k {test}']

        return ' '.join(command)

    @staticmethod
    def run_brikmock_test(
        remote_machine: str,
        polaris_sid: str,
        dev: str,
        target: str,
        test: str,
        cp: str,
        brikmock_image: str = None
    ):

        test_cmd = TestRunner.get_cmd_run_test(
            target=target,
            test=test,
            polaris_sid=polaris_sid,
            dev=dev,
            brikmock_image=brikmock_image,
            cp=cp,
            real=False
        )
        return DevMachine.run_command_on_sd_dev_box(
            remote_machine=remote_machine,
            command=test_cmd
        )

    @staticmethod
    def run_test(
        remote_machine: str,
        polaris_sid: str,
        dev: str, target: str,
        test: str
    ):
        test_cmd = TestRunner.get_cmd_run_test(
            target=target,
            test=test,
            polaris_sid=polaris_sid,
            dev=dev,
            real=True
        )
        return DevMachine.run_command_on_sd_dev_box(
            remote_machine=remote_machine,
            command=test_cmd
        )


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
        self.target_base: str = ''
        self.target_file: str = ''
        self.test: str = ''
        self.cp: str = ''
        self.sync: bool = True
        self.log_sync: bool = True
        self.dev: str = ''
        self.remote_machine: str = ''
        self.polaris_sid: str = ''


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
            logging.info('Creating empty cache file')
            with open(self.cache_file, 'wb') as _:
                pass
        except Exception as e:
            logging.error(f'Cache corrupted: {e}. Deleting')
            os.unlink(self.cache_file)
        return None


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

    def __init__(self, cache_file):
        self.last_modified = get_last_modified_time()
        self.prompt = ''
        self.sync_logs = True

        self.last_modified = None
        self.call_for_module_reload = False

        self.config: Config = Config()

        Cmd.__init__(self)
        Cache.__init__(self, cache_file)

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

        )

    def __get_resource_prompt(self):
        """Get resource prompt"""
        self.is_not_used()
        return (
            '\n-------| Resource Controls |---------\n'
            f'           dev: {self.dev}\n'
            f'remote machine: {self.remote_machine}\n'
            f'   polaris sid: {self.polaris_sid}\n'
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

    def do_set_polaris_sid(self, args):
        """Set a polaris sid."""
        self.config.polaris_sid = args
        self.save_cache_and_set_prompt()

    def do_delete_brikmock_images(self, _args):
        """Delete all brikmock images"""
        self.is_not_used()
        logging.info('Deleting all brikmock images')
        DevMachine.run_command(self.remote_machine,
                               DELETE_BRIKMOCK_DOCKER_IMAGES)

    def do_run_brikmock_test(self, args):
        """Test run"""
        maybe_sync_workspace(self.sync)
        logging.info(f'args: {args}')
        if args:
            brikmock_image = args
        else:
            brikmock_image = DevMachine.run_command(
                self.remote_machine,
                GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD,
                capture_output=True
            )[:-2]

        TestRunner.run_brikmock_test(
            remote_machine=self.remote_machine,
            polaris_sid=self.polaris_sid,
            dev=self.dev,
            target=self.target,
            test=self.test,
            cp=self.cp,
            brikmock_image=brikmock_image
        )
        maybe_sync_logs(self.log_sync, self.remote_machine)

    def do_run_brikmock_test_without_image_id(self, _):
        """Test run with no image id, this will fetch image from docker repo."""
        self.is_not_used()
        maybe_sync_workspace(self.sync)
        TestRunner.run_brikmock_test(
            remote_machine=self.remote_machine,
            polaris_sid=self.polaris_sid,
            dev=self.dev,
            target=self.target,
            test=self.test,
            cp=self.cp,
        )
        maybe_sync_logs(self.log_sync, self.remote_machine)

    def do_show_brikmock_command(self, args):
        """"""
        logging.info(f'args: {args}')
        if args:
            brikmock_image = args
        else:
            brikmock_image = DevMachine.run_command(
                remote_machine=self.remote_machine,
                command=GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD,
                capture_output=True
            )[:-2]

        command = TestRunner.get_cmd_run_test(
            target=self.target,
            test=self.test,
            polaris_sid=self.polaris_sid,
            dev=self.dev,
            brikmock_image=brikmock_image,
            cp=self.cp,
            real=False
        )
        logging.info(f'Shreyash {command}')

    def do_run_test(self, _args):
        """Test real"""
        maybe_sync_workspace(self.sync)
        TestRunner.run_test(
            remote_machine=self.remote_machine,
            polaris_sid=self.polaris_sid,
            dev=self.dev,
            target=self.target,
            test=self.test
        )
        maybe_sync_logs(self.log_sync, self.remote_machine)

    def do_sync_workspace(self, _args):
        """Sync local workspace to remote"""
        self.is_not_used()
        maybe_sync_workspace(sync=True)

    def do_sync_logs(self, _args):
        """Sync logs from remote"""
        maybe_sync_logs(self.log_sync, self.remote_machine)

    def do_open_logs(self, _args):
        """Opens the latest logs in new terminal"""
        self.is_not_used()
        LocalMachine.run_command(OPEN_LOGS_CMD)

    def do_gen_intellij_deps(self, _args):
        """Generate intellij deps."""
        maybe_sync_workspace(self.sync)
        logging.info('Generate Intellij Deps')
        DevMachine.run_command_on_sd_dev_box(
            remote_machine=self.remote_machine,
            command=REMOTE_GEN_DEPS_CMD)
        pull_workspace()

    def do_make_brikmock3_sdk_internal(self, _args):
        """
        """
        maybe_sync_workspace(self.sync)
        DevMachine.run_command_on_sd_dev_box(
            remote_machine=self.remote_machine,
            command=(
                'cd '
                'polaris/src/rubrik/sdk_internal/brikmock3'
                ' && sudo make'
            )
        )
        pull_workspace()

    def do_build_image(self, _args):
        """Build custom brikmock docker."""
        maybe_sync_workspace(self.sync)
        logging.info('Building custom brikmock image.')
        DevMachine.run_command_on_sd_dev_box(
            remote_machine=self.remote_machine,
            command=BUILD_BRIKMOCK_IMAGE_CMD
        )

    def do_start_brikmock(self, _args):
        """"""
        logging.info('Starting brikmock container on latest build')
        image_id = DevMachine.run_command(
            remote_machine=self.remote_machine,
            command=GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD,
            capture_output=True
        )[:-2]
        logging.info(f'Brikmock image id: {image_id}')
        command = [
            'ssh',
            '-t',
            f'{self.remote_machine}',
            f'docker run -p 443:443 -p 9999:9999 --name brikmock -d {image_id}'
        ]
        LocalMachine.run_command(command)
        self.do_get_brikmock(None)

    def do_stop_brikmock(self, _args):
        """Stop all brikmock containers"""
        self.is_not_used()
        logging.info('Stopping docker container')
        DevMachine.run_command(
            remote_machine=self.remote_machine,
            command=STOP_BRIKMOCK_CONTAINER_CMD
        )

    def do_get_brikmock(self, _args):
        """
        Get brikmock container API server and grpc port.
        """
        self.is_not_used()
        logging.info('Getting docker container')
        stdout = DevMachine.run_command(
            remote_machine=self.remote_machine,
            command=GET_BRIKMOCK_CONTAINER_CMD,
            capture_output=True)

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
        DevMachine.run_command_on_sd_dev_box(
            remote_machine=self.remote_machine,
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
        brikmock_image = DevMachine.run_command(
            remote_machine=self.remote_machine,
            command=GET_BRIKMOCK_DOCKER_LATEST_IMAGE_ID_CMD,
            capture_output=True
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
