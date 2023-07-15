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

        self.container.push_file_from_template(container_file_path='/etc/msmtprc',
                                               template_file_path='../templates/msmtp/msmtprc',
                                               MAIL_HOST=mail_host,
                                               MAIL_FROM_HOST=mail_from_host,
                                               MAIL_FROM_NAME=mail_from_name)

        self.container.rc_service('msmtp', 'start')

    def test(self, recipient_mail):
        self.container.pct_console_shell(f'echo test | sendmail {recipient_mail}')
