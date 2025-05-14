from broadlink_ac_mqtt.ac_communication.broadlink.connect_error import ConnectError


class ConnectTimeout(ConnectError):
    """Connection Timeout"""
    def __init__(self, code, host):
        super().__init__(code, host)
