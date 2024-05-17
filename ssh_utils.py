import tempfile

from paramiko import SSHClient, AutoAddPolicy, SSHConfig

config = SSHConfig()
config.parse(open('/Users/Shreyash.Turkar/.ssh/config'))
host_config = config.lookup('ubvm')


client = SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(AutoAddPolicy())
client.connect(
    hostname=host_config['hostname'],
    username=host_config.get('user'),
    port=int(host_config.get('port', 22)),
    key_filename=host_config['identityfile']
)
client.set_log_channel('log')

with tempfile.NamedTemporaryFile(delete=False) as tp:
    tp.write(b'hello world!')
    print(tp.name)
    tp.close()

    sftp = client.open_sftp()
    sftp.put(tp.name, f'/tmp/{tp.name.split("/")[-1]}')
    a,b,c = client.exec_command(f'cat /tmp/{tp.name.split("/")[-1]}')
    print(b.read().decode())