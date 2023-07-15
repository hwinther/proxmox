import lxc.distro.alpine.actions


class SmtpService(lxc.distro.alpine.actions.AlpineService):
    """
    Config /etc/msmtprc
    https://marlam.de/msmtp/msmtp.html
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self, mail_host: str, mail_from_host: str, mail_from_name: str):
        self.container.apk_add('msmtp')
        self.container.rc_update('msmtp', 'add')

        config_temp_path = '/tmp/msmtprc'
        config_content = open('../templates/msmtp/msmtprc', 'r').read()

        config_content = config_content.replace('MAIL_HOST', mail_host)
        config_content = config_content.replace('MAIL_FROM_HOST', mail_from_host)
        config_content = config_content.replace('MAIL_FROM_NAME', mail_from_name)

        open(config_temp_path, 'w').write(config_content)
        self.container.push_file('/etc/msmtprc', config_temp_path)

        self.container.rc_service('msmtp', 'start')

    def test(self, recipient_mail):
        self.container.pct_console_shell(f'echo test | sendmail {recipient_mail}')
