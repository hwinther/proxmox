import lxc.distro.alpine.actions
from common.common import config


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
        verbose_opt = ' -v' if config.verbose else ''
        staging_opt = ' -s' if staging else ''
        self.container.pct_console_shell(f'uacme -y{verbose_opt}{staging_opt} -c /etc/ssl/uacme new {acme_email}')

    def issue(self, domain_name: str, staging: bool = True):
        verbose_opt = ' -v' if config.verbose else ''
        staging_opt = ' -s' if staging else ''
        return self.container.pct_console_shell(f'muacme issue{verbose_opt}{staging_opt} {domain_name}')

    def ddns_update(self, operation: str, ddns_server: str, ddns_tsig_key: str, ddns_zone: str, domain_name: str,
                    ip: str):
        """
        Perform DDNS record update via knsupdate
        @param operation: add or del
        @param ddns_server: ns hostname or ip
        @param ddns_tsig_key: tsig key in the format 'algo:keyname:secret'
        @param ddns_zone: ns zone name
        @param domain_name: domain name
        @param ip: ip(v4) value
        @return: command output
        """
        return self.container.pct_console_shell(
            f"echo -e 'server {ddns_server}\nzone {ddns_zone}\nupdate {operation} {domain_name} 3600 IN A {ip}\nsend\n'"
            f" | knsupdate -y {ddns_tsig_key}")
