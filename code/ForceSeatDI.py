#
# Copyright (C) 2012-2026 MotionSystems
#
# This file is part of ForceSeatDI SDK.
#
# www.motionsystems.eu
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from ForceSeatDI_Structs import *

import ctypes
import sys

class FSDI_HandleType(ctypes.Structure):
	pass

class ForceSeatDI(object):
	def __init__(self):
		is_64bits = sys.maxsize > 2**32
		if is_64bits:
			self.lib = CDLL("ForceSeatDI64")
		else:
			self.lib = CDLL('ForceSeatDI32')

		# Create API
		self.lib.ForceSeatDI_Create.restype                 = ctypes.POINTER(FSDI_HandleType)
		self.lib.ForceSeatDI_ConnectToUsbDevice.restype     = FSDI_Bool
		self.lib.ForceSeatDI_ConnectToNetworkDevice.restype = FSDI_Bool
		self.lib.ForceSeatDI_TestConnection.restype         = FSDI_Bool
		self.lib.ForceSeatDI_Park.restype                   = FSDI_Bool
		self.lib.ForceSeatDI_SendTopTablePosPhy.restype     = FSDI_Bool
		self.lib.ForceSeatDI_SendTopTablePosPhy2.restype    = FSDI_Bool
		self.lib.ForceSeatDI_SendTopTableMatrixPhy.restype  = FSDI_Bool
		self.lib.ForceSeatDI_SendTopTableMatrixPhy2.restype = FSDI_Bool
		self.lib.ForceSeatDI_SendActuatorsPosLog.restype    = FSDI_Bool
		self.lib.ForceSeatDI_SendActuatorsPosLog2.restype   = FSDI_Bool
		self.lib.ForceSeatDI_GetPlatformInfo.restype        = FSDI_Bool
		self.lib.ForceSeatDI_GetActuatorsPosLog.restype     = FSDI_Bool
		self.lib.ForceSeatDI_GetLicenseStatus.restype       = FSDI_Bool
		self.lib.ForceSeatDI_GetTopTablePosPhy.restype      = FSDI_Bool

		self.lib.ForceSeatDI_ConnectToUsbDevice.argtypes     = ctypes.POINTER(FSDI_HandleType), c_wchar_p, c_wchar_p
		self.lib.ForceSeatDI_ConnectToNetworkDevice.argtypes = ctypes.POINTER(FSDI_HandleType), c_char_p
		self.lib.ForceSeatDI_TestConnection.argtypes         = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_Bool)
		self.lib.ForceSeatDI_Park.argtypes                   = ctypes.POINTER(FSDI_HandleType), c_uint8
		self.lib.ForceSeatDI_SendTopTablePosPhy.argtypes     = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_TopTablePositionPhysical)
		self.lib.ForceSeatDI_SendTopTablePosPhy2.argtypes    = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_TopTablePositionPhysical), ctypes.POINTER(FSDI_SFX)
		self.lib.ForceSeatDI_SendTopTableMatrixPhy.argtypes  = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_TopTableMatrixPhysical)
		self.lib.ForceSeatDI_SendTopTableMatrixPhy2.argtypes = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_TopTableMatrixPhysical), ctypes.POINTER(FSDI_SFX)
		self.lib.ForceSeatDI_SendActuatorsPosLog.argtypes    = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_RequiredActuatorsPositionLogical)
		self.lib.ForceSeatDI_SendActuatorsPosLog2.argtypes   = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_RequiredActuatorsPositionLogical), ctypes.POINTER(FSDI_SFX)
		self.lib.ForceSeatDI_GetPlatformInfo.argtypes        = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_PlatformInfo)
		self.lib.ForceSeatDI_GetActuatorsPosLog.argtypes     = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_ActualActuatorsPositionLogical)
		self.lib.ForceSeatDI_GetLicenseStatus.argtypes       = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_Bool)
		self.lib.ForceSeatDI_GetTopTablePosPhy.argtypes      = ctypes.POINTER(FSDI_HandleType), ctypes.POINTER(FSDI_ActualTopTablePositionPhysical)

		self.api = self.lib.ForceSeatDI_Create()

	def delete(self):
		self.lib.ForceSeatDI_Delete(self.api)

	def connect_to_usb_device(self, name: str = "", serialNumber: str = "") -> bool:
		result = self.lib.ForceSeatDI_ConnectToUsbDevice(self.api, name, serialNumber)
		return result == FSDI_True().value

	def connect_to_network_device(self, ipAddress: str) -> bool:
		result = self.lib.ForceSeatDI_ConnectToNetworkDevice(self.api, ipAddress.encode('utf-8'))
		return result == FSDI_True().value

	def test_connection(self, is_connected: FSDI_Bool) -> bool:
		result = self.lib.ForceSeatDI_TestConnection(self.api, byref(is_connected))
		return result == FSDI_True().value

	def park(self, park_mode: c_uint8) -> bool:
		result = self.lib.ForceSeatDI_Park(self.api, park_mode)
		return result == FSDI_True().value

	def send_top_table_pos_phy(self, position: FSDI_TopTablePositionPhysical) -> bool:
		 result = self.lib.ForceSeatDI_SendTopTablePosPhy(self.api, byref(position))
		 return result == FSDI_True().value

	def send_top_table_pos_phy2(self, position: FSDI_TopTablePositionPhysical, sfx: FSDI_SFX) -> bool:
		 result = self.lib.ForceSeatDI_SendTopTablePosPhy2(self.api, byref(position), byref(sfx))
		 return result == FSDI_True().value

	def send_top_table_matrix_phy(self, matrix: FSDI_TopTableMatrixPhysical) -> bool:
		result = self.lib.ForceSeatDI_SendTopTableMatrixPhy(self.api, byref(matrix))
		return result == FSDI_True().value
		
	def send_top_table_matrix_phy2(self, matrix: FSDI_TopTableMatrixPhysical, sfx: FSDI_SFX) -> bool:
		result = self.lib.ForceSeatDI_SendTopTableMatrixPhy2(self.api, byref(matrix), byref(sfx))
		return result == FSDI_True().value

	def send_actuators_pos_log(self, position: FSDI_RequiredActuatorsPositionLogical) -> bool:
		result = self.lib.ForceSeatDI_SendActuatorsPosLog(self.api, byref(position))
		return result == FSDI_True().value
		
	def send_actuators_pos_log2(self, position: FSDI_RequiredActuatorsPositionLogical, sfx: FSDI_SFX) -> bool:
		result = self.lib.ForceSeatDI_SendActuatorsPosLog2(self.api, byref(position), byref(sfx))
		return result == FSDI_True().value

	def get_platform_info(self, platformInfo: FSDI_PlatformInfo) -> bool:
		result = self.lib.ForceSeatDI_GetPlatformInfo(self.api, byref(platformInfo))
		return result == FSDI_True().value

	def get_actuators_pos_log(self, position: FSDI_ActualActuatorsPositionLogical) -> bool:
		result = self.lib.ForceSeatDI_GetActuatorsPosLog(self.api, byref(position))
		return result == FSDI_True().value

	def get_license_status(self, is_valid: FSDI_Bool) -> bool:
		result = self.lib.ForceSeatDI_GetLicenseStatus(self.api, byref(is_valid))
		return result == FSDI_True().value

	def get_top_table_pos_phy(self, position: FSDI_ActualTopTablePositionPhysical) -> bool:
		result = self.lib.ForceSeatDI_GetTopTablePosPhy(self.api, byref(position))
		return result == FSDI_True().value

	def get_recent_error_code(self) -> FSDI_INT32:
		return self.lib.ForceSeatDI_GetRecentErrorCode(self.api)
