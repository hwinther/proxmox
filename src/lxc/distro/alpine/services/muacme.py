import lxc.distro.alpine.actions


class AcmeService(lxc.distro.alpine.actions.AlpineService):
    """
    Config /etc/muacme/muacme.conf
    Certs dir /etc/ssl/uacme
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self, acme_email: str = None, ddns_server: str = None, ddns_tsig_key: str = None):
        self.container.apk_add('muacme knot-utils')

        config_temp_path = '/tmp/muacme.conf'
        config_content = open('../templates/muacme/muacme.conf', 'r').read()

        config_content = config_content.replace('CONFIG_DDNS_KEY', ddns_tsig_key)
        config_content = config_content.replace('CONFIG_DDNS_SERVER', ddns_server)

        open(config_temp_path, 'w').write(config_content)
        self.container.pct_console_shell(
            'mv /etc/muacme/muacme.conf /etc/muacme/muacme.conf.example')
        self.container.push_file('/etc/muacme/muacme.conf', config_temp_path)

        # weekly renewal cron script
        self.container.push_file('/etc/periodic/weekly/muacme-renew-all', '../templates/muacme/muacme-renew-all')

        # register acme user with specified email address
        self.container.pct_console_shell(f'uacme -v -c /etc/ssl/uacme -y -s new {acme_email}')

    def issue(self, dns_name):
        self.container.pct_console_shell(f'muacme issue -v -s {dns_name}')
