/*
 * Copyright (C) 2012-2026 MotionSystems
 *
 * This file is part of ForceSeatDI SDK.
 *
 * www.motionsystems.eu
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#pragma once

#include "ModuleManager.h"
#include "ForceSeatDI_Defines.h"
#include "ForceSeatDI_Structs.h"

class IForceSeatDI : public IModuleInterface
{
public:
	// Connect to USB device with given name and serial number.
	virtual bool ConnectToUsbDevice(const wchar_t* name, const wchar_t* serialNumber) = 0;

	// Connect to network device that has associated specified IP address.
	virtual bool ConnectToNetworkDevice(const char* ipAddress) = 0;

	// Check if the motion platform is connected
	virtual bool TestConnection(FSDI_Bool* isConnected) = 0;

	// Request moving to 'park' position. It might now work when motion platform is in paused mode.
	virtual bool Park(FSDI_UINT8 parkMode) = 0;

	// Call this function everytime when you want to change position of motion platform's top table (top frame)
	virtual bool SendTopTablePosLog(const FSDI_TopTablePositionLogical* position) = 0;

	// Call this function everytime when you want to change position of motion platform's top table (top frame).
	virtual bool SendTopTablePosPhy(const FSDI_TopTablePositionPhysical* position) = 0;

	// Call this function everytime when you want to change position of motion platform's top table (top frame).
	virtual bool SendTopTableMatrixPhy(const FSDI_TopTableMatrixPhysical* matrix) = 0;

	// Call this function everytime when you want to change position of actuators arms
	virtual bool SendActuatorsPosLog(const FSDI_RequiredActuatorsPositionLogical* position) = 0;

	// Call this function to get current platform status and actuators position
	virtual bool GetPlatformInfo(FSDI_PlatformInfo* platformInfo) = 0;

	// Call this function to get current actuators position
	virtual bool GetActuatorsPosLog(FSDI_ActualActuatorsPositionLogical* position) = 0;

	// Read serial number from the motion platform
	virtual bool GetSerialNumber(FSDI_Char sn[FSDI_SerialNumberStringLength]) = 0;

	// Check if license is valid:
	// * 1. If function returns 'false', then there is no connection to the motion platform. isValid is ignored.
	// * 2. If function returns 'true', then isValid contains information about license status.
	virtual bool GetLicenseStatus(FSDI_Bool* isValid) = 0;

	// Call this function to get actual top table (top frame) position in real world units.
	virtual bool GetTopTablePosPhy(FSDI_ActualTopTablePositionPhysical* position) = 0;

	// Call this function to get recent connection error code.
	virtual int32_t GetRecentErrorCode() = 0;

	static inline IForceSeatDI& Get()
	{
		return FModuleManager::LoadModuleChecked<IForceSeatDI>("ForceSeatDI");
	}

	static inline bool IsAvailable()
	{
		return FModuleManager::Get().IsModuleLoaded("ForceSeatDI");
	}
};
