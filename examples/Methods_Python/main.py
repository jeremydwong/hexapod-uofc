from ForceSeatDI import *
import os

dir = os.getcwd()

os.add_dll_directory(dir)

fsdi = ForceSeatDI()

result = fsdi.connect_to_network_device("127.0.0.1")
print("connect_to_network_device = ", result)

result = fsdi.connect_to_usb_device()
print("connect_to_usb_device       = ", result)

is_connected = FSDI_True()
print("test_connection (before)    = ", is_connected.value == FSDI_True().value)
result = fsdi.test_connection(is_connected)
print("test_connection (after)     = ", is_connected.value == FSDI_True().value)

result = fsdi.park(FSDI_ParkMode_Normal)
print("park                        = ", result)

position = FSDI_TopTablePositionPhysical()
position.structSize = sizeof(FSDI_TopTablePositionPhysical)
result = fsdi.send_top_table_pos_phy(position)
print("send_top_table_pos_phy      = ", result)

matrix = FSDI_TopTableMatrixPhysical()
matrix.structSize = sizeof(FSDI_TopTableMatrixPhysical)
matrix.transformation[0][0] = 1
matrix.transformation[1][1] = 1
matrix.transformation[2][2] = 1
matrix.transformation[3][3] = 1
result = fsdi.send_top_table_matrix_phy(matrix)
print("send_top_table_matrix_phy   = ", result)

position = FSDI_RequiredActuatorsPositionLogical()
position.structSize = sizeof(FSDI_RequiredActuatorsPositionLogical)
result = fsdi.send_actuators_pos_log(position)
print("send_actuators_pos_log      = ", result)

platformInfo = FSDI_PlatformInfo()
platformInfo.structSize = sizeof(FSDI_PlatformInfo)
result = fsdi.get_platform_info(platformInfo)
print("get_platform_info           = ", result)

position = FSDI_ActualActuatorsPositionLogical()
position.structSize = sizeof(FSDI_ActualActuatorsPositionLogical)
result = fsdi.get_actuators_pos_log(position)
print("get_actuators_pos_log       = ", result)

is_valid = FSDI_True()
print("get_license_status (before) = ", is_valid.value == FSDI_True().value)
result = fsdi.get_license_status(is_valid)
print("get_license_status (after)  = ", is_valid.value == FSDI_True().value)

position = FSDI_ActualTopTablePositionPhysical()
position.structSize = sizeof(FSDI_ActualTopTablePositionPhysical)
result = fsdi.get_top_table_pos_phy(position)
print("get_top_table_pos_phy       = ", result)

error_code = fsdi.get_recent_error_code()
print("get_recent_error_code       = ", error_code)

fsdi.delete()
