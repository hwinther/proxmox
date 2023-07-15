import lxc.distro.alpine.actions


class AcmeService(lxc.distro.alpine.actions.AlpineService):
    """
    Config /etc/muacme/muacme.conf
    Certs dir /etc/ssl/uacme
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self, acme_email: str, ddns_server: str, ddns_tsig_key: str, staging: bool = True):
        self.container.apk_add('muacme knot-utils')

        self.container.pct_console_shell(
            'mv /etc/muacme/muacme.conf /etc/muacme/muacme.conf.example')
        self.container.push_file_from_template(container_file_path='/etc/muacme/muacme.conf',
                                               template_file_path='../templates/muacme/muacme.conf',
                                               CONFIG_DDNS_KEY=ddns_tsig_key, CONFIG_DDNS_SERVER=ddns_server)

        # weekly renewal cron script
        self.container.push_file('/etc/periodic/weekly/muacme-renew-all', '../templates/muacme/muacme-renew-all')

        # register acme user with specified email address
        staging_opt = 's' if staging else ''
        self.container.pct_console_shell(f'uacme -vy{staging_opt} -c /etc/ssl/uacme new {acme_email}')

    def issue(self, dns_name, staging: bool = True):
        staging_opt = 's' if staging else ''
        self.container.pct_console_shell(f'muacme issue -v{staging_opt} {dns_name}')
