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
#ifdef _WIN32

#ifndef _MSVC_LANG
#define _MSVC_LANG 1
#endif

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif

	#include <windows.h>

	#define FSDI_LibHandle          HMODULE
	#define FSDI_GetProcAddress     GetProcAddress

#else
	#include <dlfcn.h>

	#define FSDI_LibHandle         void*
	#define FSDI_GetProcAddress    dlsym

	#define MAX_PATH               1024

#endif

#include <stdlib.h>
#include <string.h>

static  FSDI_LibHandle ForceSeatDI_LoadLibrarySecure();
static  void ForceSeatDI_FreeLibrarySecure(FSDI_LibHandle handle);

#include "ForceSeatDI_Functions.h"

typedef FSDI_Handle (*ForceSeatDI_Create_Func)                 ();
typedef void        (*ForceSeatDI_Delete_Func)                 (FSDI_Handle api);
typedef FSDI_Bool   (*ForceSeatDI_ConnectToUsbDevice_Func)     (FSDI_Handle api, const wchar_t* name, const wchar_t* serialNumber);
typedef FSDI_Bool   (*ForceSeatDI_ConnectToNetworkDevice_Func) (FSDI_Handle api, const char* ipAddress);
typedef FSDI_Bool   (*ForceSeatDI_TestConnection_Func)         (FSDI_Handle api, FSDI_Bool* isConnected);
typedef FSDI_Bool   (*ForceSeatDI_Park_Func)                   (FSDI_Handle api, FSDI_UINT8 parkMode);
typedef FSDI_Bool   (*ForceSeatDI_SendTopTablePosPhy_Func)     (FSDI_Handle api, const FSDI_TopTablePositionPhysical* position);
typedef FSDI_Bool   (*ForceSeatDI_SendTopTablePosPhy2_Func)    (FSDI_Handle api, const FSDI_TopTablePositionPhysical* position, const FSDI_SFX* sfx);
typedef FSDI_Bool   (*ForceSeatDI_SendTopTableMatrixPhy_Func)  (FSDI_Handle api, const FSDI_TopTableMatrixPhysical* matrix);
typedef FSDI_Bool   (*ForceSeatDI_SendTopTableMatrixPhy2_Func) (FSDI_Handle api, const FSDI_TopTableMatrixPhysical* matrix, const FSDI_SFX* sfx);
typedef FSDI_Bool   (*ForceSeatDI_SendActuatorsPosLog_Func)    (FSDI_Handle api, const FSDI_RequiredActuatorsPositionLogical* position);
typedef FSDI_Bool   (*ForceSeatDI_SendActuatorsPosLog2_Func)   (FSDI_Handle api, const FSDI_RequiredActuatorsPositionLogical* position, const FSDI_SFX* sfx);
typedef FSDI_Bool   (*ForceSeatDI_GetPlatformInfo_Func)        (FSDI_Handle api, FSDI_PlatformInfo* platformInfo);
typedef FSDI_Bool   (*ForceSeatDI_GetActuatorsPosLog_Func)     (FSDI_Handle api, FSDI_ActualActuatorsPositionLogical* position);
typedef FSDI_Bool   (*ForceSeatDI_GetSerialNumber_Func)        (FSDI_Handle api, FSDI_Char sn[FSDI_SerialNumberStringLength]);
typedef FSDI_Bool   (*ForceSeatDI_GetLicenseStatus_Func)       (FSDI_Handle api, FSDI_Bool* isValid);
typedef FSDI_Bool   (*ForceSeatDI_GetTopTablePosPhy_Func)      (FSDI_Handle api, FSDI_ActualTopTablePositionPhysical* position);
typedef FSDI_INT32  (*ForceSeatDI_GetRecentErrorCode_Func)     (FSDI_Handle api);
typedef FSDI_Bool   (*ForceSeatDI_GetPerformanceCounters_Func) (FSDI_Handle api, FSDI_PerformanceCounters* counters);

typedef struct ForceSeatDI_Functions
{
	ForceSeatDI_Create_Func                  Create;
	ForceSeatDI_Delete_Func                  Delete;
	ForceSeatDI_ConnectToUsbDevice_Func      ConnectToUsbDevice;
	ForceSeatDI_ConnectToNetworkDevice_Func  ConnectToNetworkDevice;
	ForceSeatDI_TestConnection_Func          TestConnection;
	ForceSeatDI_Park_Func                    Park;
	ForceSeatDI_SendTopTablePosPhy_Func      SendTopTablePosPhy;
	ForceSeatDI_SendTopTablePosPhy2_Func     SendTopTablePosPhy2;
	ForceSeatDI_SendTopTableMatrixPhy_Func   SendTopTableMatrixPhy;
	ForceSeatDI_SendTopTableMatrixPhy2_Func  SendTopTableMatrixPhy2;
	ForceSeatDI_SendActuatorsPosLog_Func     SendActuatorsPosLog;
	ForceSeatDI_SendActuatorsPosLog2_Func    SendActuatorsPosLog2;
	ForceSeatDI_GetPlatformInfo_Func         GetPlatformInfo;
	ForceSeatDI_GetActuatorsPosLog_Func      GetActuatorsPosLog;
	ForceSeatDI_GetSerialNumber_Func         GetSerialNumber;
	ForceSeatDI_GetLicenseStatus_Func        GetLicenseStatus;
	ForceSeatDI_GetTopTablePosPhy_Func       GetTopTablePosPhy;
	ForceSeatDI_GetRecentErrorCode_Func      GetRecentErrorCode;
	ForceSeatDI_GetPerformanceCounters_Func  GetPerformanceCounters;

	FSDI_LibHandle  LibraryHandle;
	FSDI_Handle     API;
} ForceSeatDI_Functions;

static void ForceSeatDI_LoadLibrary(ForceSeatDI_Functions* functions)
{
	if (! functions)
	{
		return;
	}
	memset(functions, 0, sizeof(ForceSeatDI_Functions));
	functions->LibraryHandle = ForceSeatDI_LoadLibrarySecure();
	if (functions->LibraryHandle == NULL)
	{
		return;
	}

	functions->Create                 = (ForceSeatDI_Create_Func)                 FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_Create");
	functions->Delete                 = (ForceSeatDI_Delete_Func)                 FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_Delete");
	functions->ConnectToUsbDevice     = (ForceSeatDI_ConnectToUsbDevice_Func)     FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_ConnectToUsbDevice");
	functions->ConnectToNetworkDevice = (ForceSeatDI_ConnectToNetworkDevice_Func) FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_ConnectToNetworkDevice");
	functions->TestConnection         = (ForceSeatDI_TestConnection_Func)         FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_TestConnection");
	functions->Park                   = (ForceSeatDI_Park_Func)                   FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_Park");
	functions->SendTopTablePosPhy     = (ForceSeatDI_SendTopTablePosPhy_Func)     FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_SendTopTablePosPhy");
	functions->SendTopTablePosPhy2    = (ForceSeatDI_SendTopTablePosPhy2_Func)    FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_SendTopTablePosPhy2");
	functions->SendTopTableMatrixPhy  = (ForceSeatDI_SendTopTableMatrixPhy_Func)  FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_SendTopTableMatrixPhy");
	functions->SendTopTableMatrixPhy2 = (ForceSeatDI_SendTopTableMatrixPhy2_Func) FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_SendTopTableMatrixPhy2");
	functions->SendActuatorsPosLog    = (ForceSeatDI_SendActuatorsPosLog_Func)    FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_SendActuatorsPosLog");
	functions->SendActuatorsPosLog2   = (ForceSeatDI_SendActuatorsPosLog2_Func)   FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_SendActuatorsPosLog2");
	functions->GetPlatformInfo        = (ForceSeatDI_GetPlatformInfo_Func)        FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_GetPlatformInfo");
	functions->GetActuatorsPosLog     = (ForceSeatDI_GetActuatorsPosLog_Func)     FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_GetActuatorsPosLog");
	functions->GetSerialNumber        = (ForceSeatDI_GetSerialNumber_Func)        FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_GetSerialNumber");
	functions->GetLicenseStatus       = (ForceSeatDI_GetLicenseStatus_Func)       FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_GetLicenseStatus");
	functions->GetTopTablePosPhy      = (ForceSeatDI_GetTopTablePosPhy_Func)      FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_GetTopTablePosPhy");
	functions->GetRecentErrorCode     = (ForceSeatDI_GetRecentErrorCode_Func)     FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_GetRecentErrorCode");
	functions->GetPerformanceCounters = (ForceSeatDI_GetPerformanceCounters_Func) FSDI_GetProcAddress(functions->LibraryHandle, "ForceSeatDI_GetPerformanceCounters");

	if (functions->Create                 == NULL || 
		functions->Delete                 == NULL ||
		functions->ConnectToUsbDevice     == NULL ||
		functions->ConnectToNetworkDevice == NULL ||
		functions->TestConnection         == NULL ||
		functions->Park                   == NULL ||
		functions->SendTopTablePosPhy     == NULL ||
		functions->SendTopTablePosPhy2    == NULL ||
		functions->SendTopTableMatrixPhy  == NULL ||
		functions->SendTopTableMatrixPhy2 == NULL ||
		functions->SendActuatorsPosLog    == NULL ||
		functions->SendActuatorsPosLog2   == NULL ||
		functions->GetPlatformInfo        == NULL ||
		functions->GetActuatorsPosLog     == NULL ||
		functions->GetSerialNumber        == NULL ||
		functions->GetLicenseStatus       == NULL ||
		functions->GetTopTablePosPhy      == NULL ||
		functions->GetRecentErrorCode     == NULL ||
		functions->GetPerformanceCounters == NULL)
	{
		ForceSeatDI_FreeLibrarySecure(functions->LibraryHandle);
		memset(functions, 0, sizeof(ForceSeatDI_Functions));
	}
}

static void ForceSeatDI_FreeLibrary(ForceSeatDI_Functions* functions)
{
	if (functions)
	{
		if (functions->LibraryHandle)
		{
			ForceSeatDI_FreeLibrarySecure(functions->LibraryHandle);
		}
		memset(functions, 0, sizeof(ForceSeatDI_Functions));
	}
}

FSDI_Handle FSDI_FATTR ForceSeatDI_Create()
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)malloc(sizeof(ForceSeatDI_Functions));
	ForceSeatDI_LoadLibrary(functions);
	if (! functions || ! functions->Create)
	{
		ForceSeatDI_FreeLibrary(functions);
		free(functions); // Free memory if it was reserved
		return NULL;
	}
	functions->API = functions->Create();
	return (FSDI_Handle)functions;
}

void FSDI_FATTR ForceSeatDI_Delete(FSDI_Handle api)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->Delete)
	{
		functions->Delete(functions->API);
	}
	ForceSeatDI_FreeLibrary(functions);
	free(functions);
}

FSDI_Bool FSDI_FATTR ForceSeatDI_ConnectToUsbDevice(FSDI_Handle api, const wchar_t* name, const wchar_t* serialNumber)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->ConnectToUsbDevice)
	{
		return functions->ConnectToUsbDevice(functions->API, name, serialNumber);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_ConnectToNetworkDevice(FSDI_Handle api, const char* ipAddress)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->ConnectToNetworkDevice)
	{
		return functions->ConnectToNetworkDevice(functions->API, ipAddress);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_TestConnection(FSDI_Handle api, FSDI_Bool* isConnected)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->TestConnection)
	{
		return functions->TestConnection(functions->API, isConnected);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_Park(FSDI_Handle api, FSDI_UINT8 parkMode)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->Park)
	{
		return functions->Park(functions->API, parkMode);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_SendTopTablePosPhy(FSDI_Handle api, const FSDI_TopTablePositionPhysical* position)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->SendTopTablePosPhy)
	{
		return functions->SendTopTablePosPhy(functions->API, position);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_SendTopTablePosPhy2(FSDI_Handle api, const FSDI_TopTablePositionPhysical* position, const FSDI_SFX* sfx)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->SendTopTablePosPhy2)
	{
		return functions->SendTopTablePosPhy2(functions->API, position, sfx);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_SendTopTableMatrixPhy(FSDI_Handle api, const FSDI_TopTableMatrixPhysical* matrix)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->SendTopTableMatrixPhy)
	{
		return functions->SendTopTableMatrixPhy(functions->API, matrix);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_SendTopTableMatrixPhy2(FSDI_Handle api, const FSDI_TopTableMatrixPhysical* matrix, const FSDI_SFX* sfx)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->SendTopTableMatrixPhy2)
	{
		return functions->SendTopTableMatrixPhy2(functions->API, matrix, sfx);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_SendActuatorsPosLog(FSDI_Handle api, const FSDI_RequiredActuatorsPositionLogical* position)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->SendActuatorsPosLog)
	{
		return functions->SendActuatorsPosLog(functions->API, position);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_SendActuatorsPosLog2(FSDI_Handle api, const FSDI_RequiredActuatorsPositionLogical* position, const FSDI_SFX* sfx)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->SendActuatorsPosLog2)
	{
		return functions->SendActuatorsPosLog2(functions->API, position, sfx);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_GetPlatformInfo(FSDI_Handle api, FSDI_PlatformInfo* platformInfo)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->GetPlatformInfo)
	{
		return functions->GetPlatformInfo(functions->API, platformInfo);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_GetActuatorsPosLog(FSDI_Handle api, FSDI_ActualActuatorsPositionLogical* position)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->GetActuatorsPosLog)
	{
		return functions->GetActuatorsPosLog(functions->API, position);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_GetSerialNumber(FSDI_Handle api, FSDI_Char sn[FSDI_SerialNumberStringLength])
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->GetSerialNumber)
	{
		return functions->GetSerialNumber(functions->API, sn);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_GetLicenseStatus(FSDI_Handle api, FSDI_Bool* isValid)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->GetLicenseStatus)
	{
		return functions->GetLicenseStatus(functions->API, isValid);
	}
	return FSDI_False;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_GetTopTablePosPhy(FSDI_Handle api, FSDI_ActualTopTablePositionPhysical* position)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->GetTopTablePosPhy)
	{
		return functions->GetTopTablePosPhy(functions->API, position);
	}
	return FSDI_False;
}

FSDI_INT32 FSDI_FATTR ForceSeatDI_GetRecentErrorCode(FSDI_Handle api)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->GetRecentErrorCode)
	{
		return functions->GetRecentErrorCode(functions->API);
	}
	return -1;
}

FSDI_Bool FSDI_FATTR ForceSeatDI_GetPerformanceCounters(FSDI_Handle api, FSDI_PerformanceCounters* counters)
{
	ForceSeatDI_Functions* functions = (ForceSeatDI_Functions*)api;
	if (functions && functions->GetPerformanceCounters)
	{
		return functions->GetPerformanceCounters(functions->API, counters);
	}
	return FSDI_False;
}

FSDI_LibHandle ForceSeatDI_LoadLibrarySecure()
{
#ifdef _WIN32
	#ifdef _M_X64
		static const wchar_t* const LIBRARY_DLL_NAME = L"ForceSeatDI64.dll";
	#else
		static const wchar_t* const LIBRARY_DLL_NAME = L"ForceSeatDI32.dll";
	#endif

	HMODULE hLibrary = LoadLibraryW(LIBRARY_DLL_NAME);

	// Let's try in parent paths
	if (hLibrary == NULL)
	{
		wchar_t buffer[MAX_PATH * 2] = {0};
		wcscpy_s(buffer, MAX_PATH * 2, L"..\\..\\..\\");
		wcscat_s(buffer, MAX_PATH * 2, LIBRARY_DLL_NAME);
		hLibrary = LoadLibraryW(buffer);
	}
	return hLibrary;
#else
	#if defined(__x86_64) || defined(__aarch64__) || defined(_M_ARM64)
		static const char* const LIBRARY_DLL_NAME = "./ForceSeatDI64.so";
	#else
		static const char* const LIBRARY_DLL_NAME = "./ForceSeatDI32.so";
	#endif

	FSDI_LibHandle hLibrary = dlopen(LIBRARY_DLL_NAME, RTLD_LAZY);
	return hLibrary;
#endif
}

void ForceSeatDI_FreeLibrarySecure(FSDI_LibHandle handle)
{
#ifdef _WIN32
	FreeLibrary(handle);
#else
	dlclose(handle);
#endif
}
