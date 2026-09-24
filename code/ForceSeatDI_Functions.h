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
#ifndef FORCE_SEAT_DI_FUNCTIONS_H
#define FORCE_SEAT_DI_FUNCTIONS_H

/*
 * This file defines pure C interface for ForceSeatDI.
 * Check examples for details.
 */

#include "ForceSeatDI_Structs.h"
#include "wchar.h"

#ifdef __cplusplus
extern "C" {
#endif

	struct __FSDI_HandleType { int unused; };
	typedef struct __FSDI_HandleType* FSDI_Handle;

	/*
	 * Call this function to create instance of the API. Until this call no objects
	 * are created in library in order to avoid initialization problems. Remember
	 * to call ForceSeatDI_Delete when you finish.
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Handle FSDI_FATTR ForceSeatDI_Create();

	/*
	 * Call this function to release the API object.
	 */
	FORCESEAT_DI_EXPORT
	void FSDI_FATTR ForceSeatDI_Delete(FSDI_Handle api);

	/*
	 * Connect to USB device with given name and serial number.
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_ConnectToUsbDevice(FSDI_Handle api, const wchar_t* name, const wchar_t* serialNumber);

	/*
	 * Connect to network device that has associated specified IP address.
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_ConnectToNetworkDevice(FSDI_Handle api, const char* ipAddress);

	/*
	 * Check if the motion platform is connected
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_TestConnection(FSDI_Handle api, FSDI_Bool* isConnected);

	/*
	 * Request moving to 'park' position. It might now work when motion platform is in paused mode.
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_Park(FSDI_Handle api, FSDI_UINT8 parkMode/* one of FSDI_ParkMode */);

	/*
	 * Call this function everytime when you want to change position of motion platform's top table (top frame).
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_SendTopTablePosPhy(FSDI_Handle api,
	                                                    const FSDI_TopTablePositionPhysical* position);

	/*
	 * Call this function everytime when you want to change position of motion platform's top table (top frame).
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_SendTopTableMatrixPhy(FSDI_Handle api,
	                                                       const FSDI_TopTableMatrixPhysical* matrix);

	/*
	 * Call this function everytime when you want to change position of actuators arms
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_SendActuatorsPosLog(FSDI_Handle api,
	                                                     const FSDI_RequiredActuatorsPositionLogical* position);

	/*
	 * Call this function to get current platform status and actuators position
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_GetPlatformInfo(FSDI_Handle api,
	                                                 FSDI_PlatformInfo* platformInfo);

	/*
	 * Call this function to get current actuators position
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_GetActuatorsPosLog(FSDI_Handle api,
	                                                    FSDI_ActualActuatorsPositionLogical* position);

	/*
	 * Read serial number from the motion platform
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_GetSerialNumber(FSDI_Handle api, FSDI_Char sn[FSDI_SerialNumberStringLength]);

	/*
	 * Check if license is valid:
	 * 1. If function returns 'false', then there is no connection to the motion platform. isValid is ignored.
	 * 2. If function returns 'true', then isValid contains information about license status.
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_GetLicenseStatus(FSDI_Handle api, FSDI_Bool* isValid);

	/*
	 * Call this function to get actual top table (top frame) position in real world units.
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_GetTopTablePosPhy(FSDI_Handle api,
	                                                   FSDI_ActualTopTablePositionPhysical* position);

	/*
	 * Call this function to get recent connection error code.
	 */
	FORCESEAT_DI_EXPORT
	FSDI_INT32 FSDI_FATTR ForceSeatDI_GetRecentErrorCode(FSDI_Handle api);

	/*
	 * Call this function everytime when you want to change position of motion platform's top table (top frame).
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_SendTopTablePosPhy2(FSDI_Handle api,
	                                                     const FSDI_TopTablePositionPhysical* position,
	                                                     const FSDI_SFX* sfx);

	/*
	 * Call this function everytime when you want to change position of motion platform's top table (top frame).
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_SendTopTableMatrixPhy2(FSDI_Handle api,
	                                                        const FSDI_TopTableMatrixPhysical* matrix,
	                                                        const FSDI_SFX* sfx);

	/*
	 * Call this function everytime when you want to change position of actuators arms
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_SendActuatorsPosLog2(FSDI_Handle api,
	                                                      const FSDI_RequiredActuatorsPositionLogical* position,
	                                                      const FSDI_SFX* sfx);

	/*
	 * Call this function to get recent performance counters
	 */
	FORCESEAT_DI_EXPORT
	FSDI_Bool FSDI_FATTR ForceSeatDI_GetPerformanceCounters(FSDI_Handle api,
	                                                        FSDI_PerformanceCounters* counters);

#ifdef __cplusplus
}
#endif

#endif
