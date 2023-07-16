import lxc.distro.alpine.actions


class NginxService(lxc.distro.alpine.actions.AlpineService):
    """
    Config xx
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self, domain_name: str):
        self.container.apk_add('nginx')
        self.container.rc_update('nginx', 'add')

        # TODO: firewall policy?
        self.container.push_file_from_template(container_file_path='/etc/nginx/http.d/jellyfin.conf',
                                               template_file_path='../templates/nginx/jellyfin.conf',
                                               DOMAIN_NAME=domain_name)

        self.container.pct_console_shell('mkdir /etc/nginx/ssl')
        # if this takes a long time run 'apt install haveged' on the PVE host
        self.container.pct_console_shell('openssl dhparam -out /etc/nginx/ssl/dhparam.pem 4096')
        self.container.push_file(container_file_path='/etc/nginx/ssl/options-ssl-nginx.conf',
                                 local_file_path='../templates/nginx/options-ssl-nginx.conf')

        self.container.rc_service('nginx', 'start')
