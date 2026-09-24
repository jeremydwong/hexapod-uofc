from ForceSeatDI import *
import math
import os
import time

dir = os.getcwd()

os.add_dll_directory(dir)

fsdi = ForceSeatDI()

result = fsdi.connect_to_usb_device()
print("connect_to_usb_device       = ", result)

if (result):
    is_connected = FSDI_True()
    result = fsdi.test_connection(is_connected)
    print("test_connection (after)     = ", is_connected.value == FSDI_True().value)

    if (is_connected):
        is_valid = FSDI_True()
        result = fsdi.get_license_status(is_valid)
        print("get_license_status          = ", is_valid.value == FSDI_True().value)
        
        is_valid = FSDI_True()

        if (is_valid):
            iterator = 0
            maxRoll  = 10
            position                     = FSDI_TopTablePositionPhysical()
            position.structSize          = sizeof(FSDI_TopTablePositionPhysical)
            position.maxSpeed            = 65535
            position.pause               = FSDI_False()
            position.strategy            = 0
            position.accelerationProfile = 0

            platformInfo = FSDI_PlatformInfo()
            platformInfo.structSize = sizeof(FSDI_PlatformInfo)

            actuatorsPosition = FSDI_ActualActuatorsPositionLogical()
            actuatorsPosition.structSize = sizeof(FSDI_ActualActuatorsPositionLogical)

            topTablePositionPhysical= FSDI_ActualTopTablePositionPhysical()
            topTablePositionPhysical.structSize = sizeof(FSDI_ActualTopTablePositionPhysical)

            print("SIM started")
            while (iterator < 2000):
                position.roll = math.sin(iterator * 3.1415 / 180) * maxRoll * 3.1415 / 180
                fsdi.send_top_table_pos_phy(position)
                iterator = iterator + 3

                fsdi.get_platform_info(platformInfo)
                fsdi.get_actuators_pos_log(actuatorsPosition)
                fsdi.get_top_table_pos_phy(topTablePositionPhysical)
                errorCode = fsdi.get_recent_error_code()

                time.sleep(0.005)

            print("SIM ended")

fsdi.delete()
