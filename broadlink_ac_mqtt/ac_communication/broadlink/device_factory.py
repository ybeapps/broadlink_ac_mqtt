from broadlink_ac_mqtt.ac_communication.broadlink.ac_db import ac_db
from broadlink_ac_mqtt.ac_communication.broadlink.ac_db_debug import ac_db_debug
from broadlink_ac_mqtt.ac_communication.broadlink.ac_db_disconnected import ac_db_disconnected
from broadlink_ac_mqtt.ac_communication.broadlink.device import device


def create_device(dev_type, host, mac, name=None, cloud=None, update_interval=0):
    # print format(dev_type,'02x')
    match dev_type:
        # We only care about 1 device type...
        case 0x4E2a:  # Danham Bush
            return ac_db(host=host, mac=mac, name=name, cloud=cloud, devtype=dev_type, update_interval=0)
        case 0xFFFFFFF:  # test
            return ac_db_debug(host=host, mac=mac, name=name, cloud=cloud, devtype=dev_type, update_interval=0)
        case 0x0000000:
            return ac_db_disconnected(dev_type=dev_type)
        case _:
            return device(host=host, mac=mac, devtype=dev_type, update_interval=update_interval)
