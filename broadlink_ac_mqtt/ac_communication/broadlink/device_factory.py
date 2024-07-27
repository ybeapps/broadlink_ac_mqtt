from broadlink_ac_mqtt.ac_communication.broadlink.ac_db import ac_db
from broadlink_ac_mqtt.ac_communication.broadlink.ac_db_debug import ac_db_debug
from broadlink_ac_mqtt.ac_communication.broadlink.device import device


def gendevice(devtype, host, mac, name=None, cloud=None, update_interval=0):
    # print format(devtype,'02x')
    ##We only care about 1 device type...
    if devtype == 0x4E2a:  # Danham Bush
        return ac_db(host=host, mac=mac, name=name, cloud=cloud, devtype=devtype, update_interval=0)
    if devtype == 0xFFFFFFF:  # test
        return ac_db_debug(host=host, mac=mac, name=name, cloud=cloud, devtype=devtype, update_interval=0)
    else:
        return device(host=host, mac=mac, devtype=devtype, update_interval=update_interval)
