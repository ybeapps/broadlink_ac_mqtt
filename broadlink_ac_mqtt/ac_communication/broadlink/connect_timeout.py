from broadlink_ac_mqtt.ac_communication.broadlink.connect_error import ConnectError


class ConnectTimeout(ConnectError):
    """Connection Timeout"""
    pass
