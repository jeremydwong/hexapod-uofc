/*
 * Copyright (C) 2012-2026 MotionSystems
 *
 * This file is part of ForceSeatDI SDK.
 *
 * www.motionsystems.eu
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 * -------------------------------------------------------------------------------------------------------
 *
 * This example uses ForceSeatDI to show how to connect up to 4 motion units at the same time
 * and control them with Inverse Kinematics
 */

#include <stdio.h>
#include <string.h>
#include <math.h>
#include <vector>
#include <algorithm>
#include <unistd.h>
#include <time.h>
#include <dlfcn.h>
#include <stdint.h>

#include "ForceSeatDI.h"

namespace
{
	void sleepMS(unsigned int ms)
	{
		usleep(ms * 1000);
	}

	bool prepareAPI(std::vector<FSDI_Handle>& apis, uint32_t index)
	{
		apis.resize(index + 1);
		if (apis[index] == nullptr)
		{
			apis[index] = ForceSeatDI_Create();
		}

		if (apis[index] == nullptr)
		{
			printf("ForceSeatDI .so was not loaded, dlopen result = %s\n", dlerror());
			return false;
		}

		return true;
	}

	bool checkPlatform(const std::vector<FSDI_Handle>& apis, uint32_t index)
	{
		FSDI_Char sn[FSDI_SerialNumberStringLength];
		if (ForceSeatDI_GetSerialNumber(apis[index], sn) != FSDI_True)
		{
			printf("Failed to get platform info from %d\n", (index + 1));
			return false;
		}

		printf("Platform %d S/N: %s\n", (index + 1), reinterpret_cast<const char*>(sn));

		FSDI_Bool isLicenseValid = FSDI_False;
		if (ForceSeatDI_GetLicenseStatus(apis[index], &isLicenseValid) != FSDI_True)
		{
			printf("Failed to get license status from %d\n", (index + 1));
			return false;
		}

		if (isLicenseValid != FSDI_True)
		{
			printf("License is not valid for %d\n", (index + 1));
			return false;
		}
		return true;
	}

	bool connectNET(std::vector<FSDI_Handle>& apis, uint32_t index, const char* ipAddress)
	{
		if (! prepareAPI(apis, index))
		{
			return false;
		}

		if (ForceSeatDI_ConnectToNetworkDevice(apis[index], ipAddress) != FSDI_True)
		{
			printf("Failed to connect to %s, error: %d\n",
				   (ipAddress ? ipAddress : "NULL"),
				   ForceSeatDI_GetRecentErrorCode(apis[index]));
			return false;
		}

		return checkPlatform(apis, index);
	}

	bool connectUSB(std::vector<FSDI_Handle>& apis, uint32_t index, const wchar_t* sn)
	{
		if (! prepareAPI(apis, index))
		{
			return false;
		}

		if (ForceSeatDI_ConnectToUsbDevice(apis[index], nullptr, sn) != FSDI_True)
		{
			wprintf(L"Failed to connect to %ls, error: %d\n",
					(sn ? sn : L"NULL"),
					ForceSeatDI_GetRecentErrorCode(apis[index]));
			return false;
		}

		return checkPlatform(apis, index);
	}

	void send(const std::vector<FSDI_Handle>& apis, uint32_t index, const FSDI_TopTablePositionPhysical& pos)
	{
		if (ForceSeatDI_SendTopTablePosPhy(apis[index], &pos) != FSDI_True)
		{
			printf("Failed to send request to platform %d\n", (index + 1));
		}
	}

	void work(std::vector<FSDI_Handle>& apis)
	{
		bool ok = true;

		(void)&connectNET;
		(void)&connectUSB;

#if 0
		// Network 4 devices
		ok = ok &&  connectNET(apis, 0, "10.1.1.75");
		ok = ok &&  connectNET(apis, 1, "10.1.1.75");
		ok = ok &&  connectNET(apis, 2, "10.1.1.75");
		ok = ok &&  connectNET(apis, 3, "10.1.1.75");
#endif
#if 0
		// USB 4 devices
		ok = ok &&  connectUSB(apis, 0, L"250031-000457-315839-323120");
		ok = ok &&  connectUSB(apis, 1, L"250031-000457-315839-323120");
		ok = ok &&  connectUSB(apis, 2, L"250031-000457-315839-323120");
		ok = ok &&  connectUSB(apis, 3, L"250031-000457-315839-323120");
#endif
#if 1
		// USB 1 any device
		ok = ok &&  connectUSB(apis, 0, nullptr);
#endif

		if (! ok)
		{
			return;
		}

		sleepMS(500);
		const auto NumberOfPlatforms = static_cast<uint32_t>(apis.size());

		FSDI_TopTablePositionPhysical  pos;
		memset(&pos, 0, sizeof(pos));
		pos.structSize = sizeof(pos);
		pos.maxSpeed = 65535;
		pos.pause = FSDI_False;
		pos.strategy = FSDI_Strategy_BestMatch;
		pos.accelerationProfile = FSDI_AP_Auto;

		std::vector<FSDI_ActualActuatorsPositionLogical> actualPositions;
		std::vector<FSDI_PlatformInfo>                   platformInfos;
		std::vector<FSDI_ActualTopTablePositionPhysical> topTablePos;
		actualPositions.resize(NumberOfPlatforms);
		platformInfos.resize(NumberOfPlatforms);
		topTablePos.resize(NumberOfPlatforms);

		for (uint32_t i = 0; i < NumberOfPlatforms; ++i)
		{
			actualPositions[i].structSize = sizeof(FSDI_ActualActuatorsPositionLogical);
			platformInfos[i].structSize   = sizeof(FSDI_PlatformInfo);
			topTablePos[i].structSize = sizeof(FSDI_ActualTopTablePositionPhysical);
		}

		unsigned int iterator = 0;

		printf("SIM started...\n");
		while (true)
		{
			// Prepare demo data
			auto value = sinf(iterator * 3.1415f / 180) * 5 * 3.1415f / 180;
			if (++iterator > 360)
			{
				iterator = 0;
			}

			pos.roll  = value;
			pos.pitch = 0;
			send(apis, 0, pos);

			if (NumberOfPlatforms > 1)
			{
				pos.roll = -value;
				pos.pitch = 0;
				send(apis, 1, pos);
			}

			if (NumberOfPlatforms > 2)
			{
				pos.roll  = 0;
				pos.pitch = value;
				send(apis, 2, pos);
			}

			if (NumberOfPlatforms > 3)
			{
				pos.roll  = 0;
				pos.pitch = -value;
				send(apis, 3, pos);
			}

			// Read current actuators position
			for (uint32_t i = 0; i < NumberOfPlatforms; ++i)
			{
				if (ForceSeatDI_GetActuatorsPosLog(apis[i], &actualPositions[i]) != FSDI_True)
				{
					printf("Failed to get actuator pos from %u\n", (i + 1));
				}
				if (ForceSeatDI_GetTopTablePosPhy(apis[i], &topTablePos[i]) != FSDI_True)
				{
					printf("Failed to get top table pos from %u\n", (i + 1));
				}
				if (ForceSeatDI_GetPlatformInfo(apis[i], &platformInfos[i]) != FSDI_True)
				{
					printf("Failed to get platform info from %u\n", (i + 1));
					printf("ErrorCode: %d", ForceSeatDI_GetRecentErrorCode(apis[i]));
				}
			}

#if 1
			// NOTE: Displaying data is slow
			for (uint32_t i = 0; i < NumberOfPlatforms; ++i)
			{
				printf("Platform: %u, Pos: %u, %u, %u, %u, %u, %u\n",
					(i + 1),
					actualPositions[i].actualMotorPosition[0],
					actualPositions[i].actualMotorPosition[1],
					actualPositions[i].actualMotorPosition[2],
					actualPositions[i].actualMotorPosition[3],
					actualPositions[i].actualMotorPosition[4],
					actualPositions[i].actualMotorPosition[5]);
				printf("    Error code: %d.%d\n", 
					static_cast<int>(platformInfos[i].moduleErrorCode), 
					static_cast<int>(platformInfos[i].moduleErrorIndex));
				printf("    Top Frame: roll %f, pitch %f, yaw %f, heave %f, surge %f, sway %f\n",
					topTablePos[i].roll,
					topTablePos[i].pitch,
					topTablePos[i].yaw,
					topTablePos[i].heave,
					topTablePos[i].surge,
					topTablePos[i].sway);
				static_assert(FSDI_MotorsCount == 6, "");
			}
#endif

			sleepMS(5);
		}
		printf("SIM ended...\n");
	}
}

int main(int argc, char* argv[])
{
	(void)argc;
	(void)argv;
	std::vector<FSDI_Handle> apis;
	work(apis);

	for (FSDI_Handle api : apis)
	{
		ForceSeatDI_Park(api, FSDI_ParkMode_Normal);
		ForceSeatDI_Delete(api);
	}
	return 0;
}
