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
 *
 */

#include <chrono>
#include <fstream>
#include <iostream>
#include <thread>
#include <vector>

#include "ForceSeatDI.h"
#include "MSU_GyroPlayer.h"

namespace
{
	const int MAX_SPEED               = 65535;
	const int MAX_POS                 = 65535;
	const int INTERVAL_MS             = 10;
	const int WAKE_UP_INTERVAL_MS     = 10000;
	const float WAKE_UP_SIGNAL_AMP_MM = 5;
	const float WAKE_UP_SIGNAL_FREQ   = 0.25f;
	const float DEG_TO_RAD            = 0.01745329252f;
	const char* OUTPUT_FILE           = "output.csv";

	struct Entry
	{
		uint64_t time_ms;
		float    given_roll;
		float    given_pitch;
		float    given_yaw;
		float    given_sway;
		float    given_surge;
		float    given_heave;
		float    actual_roll;
		float    actual_pitch;
		float    actual_yaw;
		float    actual_sway;
		float    actual_surge;
		float    actual_heave;
	};

	struct CallbackContext
	{
		FSDI_Handle                          api;
		FSDI_TopTablePositionPhysical*       position;
		FSDI_ActualTopTablePositionPhysical* topTablePosition;
		std::vector<Entry>*                  entries;
		uint64_t                             startTime;
	};

	uint64_t currentTime()
	{
		return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
	}

	float sinus(uint64_t time, float hz, float amplitude, float valueOffset)
	{
		return amplitude * sin(hz * time * 0.001f * 2.0f * 3.1415f) + valueOffset;
	}

	void callback(const MSU_GyroPlayerData* data, void* userData)
	{
		auto context = reinterpret_cast<CallbackContext*>(userData);

		if (0 == context->startTime)
		{
			context->startTime = currentTime();
		}

		context->position->roll  = data->roll;
		context->position->pitch = data->pitch;
		context->position->yaw   = data->yaw;
		context->position->sway  = data->sway;
		context->position->surge = data->surge;
		context->position->heave = data->heave;

		ForceSeatDI_SendTopTablePosPhy(context->api, context->position);

		if (FSDI_True == ForceSeatDI_GetTopTablePosPhy(context->api, context->topTablePosition))
		{
			context->entries->push_back(
				{
					currentTime() - context->startTime,
					data->roll,
					data->pitch,
					data->yaw,
					data->sway,
					data->surge,
					data->heave,
					context->topTablePosition->roll,
					context->topTablePosition->pitch,
					context->topTablePosition->yaw,
					context->topTablePosition->sway,
					context->topTablePosition->surge,
					context->topTablePosition->heave
				}
			);
		}
		else
		{
			std::cout << "Failed to get top table position!" << std::endl;
		}
	}
}

int wmain(int argc, wchar_t** argv)
{
	std::cout << std::endl;
	std::cout << "Application has been started." << std::endl;

	auto player = MSU_GyroPlayer_Create();

	if (!player)
	{
		std::cout << "Failed to create CSV file reader!" << std::endl;
		return -1;
	}

	MSU_GyroPlayer_SetCsvSkipLines(player, 1);

	MSU_GyroPlayer_SetCsvMapping(player, 1, MSU_GPR_Roll,  MSU_GPR_NotInverted /* no invertion*/, 1.0f);
	MSU_GyroPlayer_SetCsvMapping(player, 2, MSU_GPR_Pitch, MSU_GPR_NotInverted /* no invertion*/, 1.0f);
	MSU_GyroPlayer_SetCsvMapping(player, 3, MSU_GPR_Yaw,   MSU_GPR_NotInverted /* no invertion*/, 1.0f);
	MSU_GyroPlayer_SetCsvMapping(player, 4, MSU_GPR_Sway,  MSU_GPR_NotInverted /* no invertion*/, 1.0f);
	MSU_GyroPlayer_SetCsvMapping(player, 5, MSU_GPR_Surge, MSU_GPR_NotInverted /* no invertion*/, 1.0f);
	MSU_GyroPlayer_SetCsvMapping(player, 6, MSU_GPR_Heave, MSU_GPR_NotInverted /* no invertion*/, 1.0f);

	if (argc != 3)
	{
		std::cout << "CSV files not specified!" << std::endl;
		MSU_GyroPlayer_Delete(player);
		return -1;
	}

	std::wstring file(argv[1]);
	std::wcout << L"Loading CSV (" << file.c_str() << ")" << std::endl;

	auto result = MSU_GyroPlayer_LoadCsv(player, file.c_str(), ';', INTERVAL_MS, MSU_GPR_Milliseconds);
	auto entryCount = MSU_GyroPlayer_GetEntryCount(player);

	if (MSU_GPEC_Ok != result || 0 >= entryCount)
	{
		std::cout << "Failed to load CSV, error code: " << result << std::endl;
		MSU_GyroPlayer_Delete(player);
		return -1;
	}

	std::vector<Entry> entries;
	entries.reserve(entryCount);

	FSDI_ActualTopTablePositionPhysical topTablePosition;
	memset(&topTablePosition, 0, sizeof(topTablePosition));
	topTablePosition.structSize = sizeof(topTablePosition);

	FSDI_TopTablePositionPhysical position;
	memset(&position, 0, sizeof(position));

	position.structSize          = sizeof(position);
	position.maxSpeed            = MAX_SPEED;
	position.pause               = FSDI_False;
	position.strategy            = FSDI_Strategy_BestMatch;
	position.accelerationProfile = FSDI_AP_Auto;

	CallbackContext context;
	memset(&context, 0, sizeof(context));

	context.api              = ForceSeatDI_Create();
	context.position         = &position;
	context.topTablePosition = &topTablePosition;
	context.entries          = &entries;

	if (nullptr == context.api)
	{
		std::cout << "Failed to load ForceSeatDI DLL" << std::endl;
		MSU_GyroPlayer_Delete(player);
		return -1;
	}

	if (FSDI_True != ForceSeatDI_ConnectToUsbDevice(context.api, nullptr, nullptr))
	{
		std::cout << "Failed to connect to the USB device, error: " << ForceSeatDI_GetRecentErrorCode(context.api) << std::endl;
		MSU_GyroPlayer_Delete(player);
		ForceSeatDI_Delete(context.api);
		return -1;
	}

	FSDI_Bool isValid = FSDI_False;
	ForceSeatDI_GetLicenseStatus(context.api, &isValid);

	if (!isValid)
	{
		std::cout << "There is no connection or license status is not valid!" << std::endl;
		MSU_GyroPlayer_Delete(player);
		ForceSeatDI_Delete(context.api);
		return -1;
	}

	std::cout << "Waking up the machine" << std::endl;

	uint64_t elapsed = 0;
	uint64_t startTime = currentTime();

	do
	{
		elapsed = currentTime() - startTime;

		context.position->heave = sinus(elapsed, WAKE_UP_SIGNAL_FREQ, WAKE_UP_SIGNAL_AMP_MM, 0);

		ForceSeatDI_SendTopTablePosPhy(context.api, context.position);

		std::this_thread::sleep_for(std::chrono::milliseconds(5));

	} while (elapsed < WAKE_UP_INTERVAL_MS);

	std::cout << "Sending CSV data to the machine" << std::endl;

	result = MSU_GyroPlayer_PlayAsync(player, &callback, &context);

	if (MSU_GPEC_Ok != result)
	{
		std::cout << "Failed to play CSV, error code: " << result << std::endl;
		MSU_GyroPlayer_Delete(player);
		ForceSeatDI_Park(context.api, FSDI_ParkMode_Normal);
		ForceSeatDI_Delete(context.api);
		return -1;
	}

	MSU_GyroPlayer_Wait(player);
	MSU_GyroPlayer_Delete(player);

	std::cout << "Sending data has been finished" << std::endl;

	ForceSeatDI_Park(context.api, FSDI_ParkMode_Normal);
	ForceSeatDI_Delete(context.api);

	std::cout << "Saving output file" << std::endl;

	std::wstring outFileName(argv[2]);
	std::ofstream outFile;
	outFile.open(outFileName, std::ios::out | std::ios::trunc);
	outFile << "time_ms;"
			<< "given_roll_rad;"
			<< "given_pitch_rad;"
			<< "given_yaw_rad;"
			<< "given_sway_mm;"
			<< "given_surge_mm;"
			<< "given_heave_mm;"
			<< "actual_roll_rad;"
			<< "actual_pitch_rad;"
			<< "actual_yaw_rad;"
			<< "actual_sway_mm;"
			<< "actual_surge_mm;"
			<< "actual_heave_mm" << std::endl;

	for (auto& entry : entries)
	{
		outFile << entry.time_ms      << ";";
		outFile << entry.given_roll   << ";";
		outFile << entry.given_pitch  << ";";
		outFile << entry.given_yaw    << ";";
		outFile << entry.given_sway   << ";";
		outFile << entry.given_surge  << ";";
		outFile << entry.given_heave  << ";";
		outFile << entry.actual_roll  << ";";
		outFile << entry.actual_pitch << ";";
		outFile << entry.actual_yaw   << ";";
		outFile << entry.actual_sway  << ";";
		outFile << entry.actual_surge << ";";
		outFile << entry.actual_heave << std::endl;
	}

	outFile.close();

	std::cout << "Successfully completed" << std::endl;

	return 0;
}
