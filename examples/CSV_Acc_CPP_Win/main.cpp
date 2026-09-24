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
	static constexpr const int   MAX_SPEED             = 65535;
	static constexpr const int   SAMPLES_INTERVAL_MS   = 0; // zero means that no sample are ignored and GyroPlayer does not wait between callback calls
	static constexpr const int   MSG_INTERVAL_MS       = 4;
	static constexpr const int   WAKE_UP_INTERVAL_MS   = 10000;
	static constexpr const float WAKE_UP_SIGNAL_AMP_MM = 5;
	static constexpr const float WAKE_UP_SIGNAL_FREQ   = 0.25f;

	struct Entry
	{
		uint64_t time_ms;
		float    given_sway_acc;
		float    given_surge_acc;
		float    given_heave_acc;
		float    calc_sway_mm;
		float    calc_surge_mm;
		float    calc_heave_mm;
		float    actual_sway_mm;
		float    actual_surge_mm;
		float    actual_heave_mm;
	};

	class Timer
	{
	public:
		typedef std::chrono::high_resolution_clock::time_point TimePoint;

		Timer()
		{
			Restart();
		}

		void Restart()
		{
			m_start = std::chrono::high_resolution_clock::now();
		}

		uint64_t Elapsed_ms() const
		{
			auto now = std::chrono::high_resolution_clock::now();
			std::chrono::duration<double, std::milli> elapsed(now - m_start);
			return static_cast<uint64_t>(elapsed.count());
		}

		void WaitUntil_ms(uint64_t time)
		{
			auto awakeTime = m_start + std::chrono::milliseconds(time);
			std::this_thread::sleep_until(awakeTime);
		}

	private:
		TimePoint m_start;
	};

	struct CallbackContext
	{
		FSDI_Handle                          api;
		FSDI_TopTablePositionPhysical*       position;
		FSDI_ActualTopTablePositionPhysical* topTablePosition;
		std::vector<Entry>*                  entries;
		Timer                                timer;
		uint64_t                             lastMsgTimeMark_us;
		uint64_t                             previousSampleTimeMark_us;
		bool                                 firstCall;
		
		struct
		{
			float velocity;
			float displacement;
		} sway, surge, heave;
	};

	float warmupSinus(uint64_t time, float hz, float amplitude, float valueOffset)
	{
		return amplitude * sin(hz * time * 0.001f * 2.0f * 3.1415f) + valueOffset;
	}

	void callback(const MSU_GyroPlayerData* data, void* userData)
	{
		auto* context = reinterpret_cast<CallbackContext*>(userData);

		if (context->firstCall)
		{ 
			context->firstCall                 = false;
			context->previousSampleTimeMark_us = data->timestamp_us;
			context->lastMsgTimeMark_us        = data->timestamp_us;;
			context->timer.Restart();
		}

		// Interval between samples might not be constant, so calculate dT each callback call
		float dTime_s = 0.000001f * (data->timestamp_us - context->previousSampleTimeMark_us);
		context->previousSampleTimeMark_us = data->timestamp_us;

		context->sway.displacement   += context->sway.velocity  * dTime_s + data->accSway  * (dTime_s * dTime_s * 0.5f);
		context->surge.displacement  += context->surge.velocity * dTime_s + data->accSurge * (dTime_s * dTime_s * 0.5f);
		context->heave.displacement  += context->heave.velocity * dTime_s + data->accHeave * (dTime_s * dTime_s * 0.5f);

		context->sway.velocity  += data->accSway  * dTime_s;
		context->surge.velocity += data->accSurge * dTime_s;
		context->heave.velocity += data->accHeave * dTime_s;

		context->position->roll  = 0;
		context->position->pitch = 0;
		context->position->yaw   = 0;
		context->position->sway  = context->sway.displacement  * 1000 /* m to mm */;
		context->position->surge = context->surge.displacement * 1000 /* m to mm */;
		context->position->heave = context->heave.displacement * 1000 /* m to mm */;

		// NOTE: Without a washout algorithm, the top table may leave the work area quite quickly 
		// if input data recording was not started when the vehicle was at rest. In other words, 
		// the vehicle's velocities and accelerations should be 0 when input recording begins, 
		// otherwise the pre-existing vehicle velocities and accelerations will be unknown, 
		// and as a result, the top table may drift away from the center.

		if (data->timestamp_us - context->lastMsgTimeMark_us >= 1000 * MSG_INTERVAL_MS)
		{
			// If SAMPLES_INTERVAL_MS is set to 0, then MSU_GyroPlayer does not waits between 'callback' calls.
			// It means that in 'callback' function we need to make sure that new control data is not sent too often.
			// In other words, we want to do math on all samples to achieve higher precision but only send data
			// to the motion platform every MSG_INTERVAL_MS.
			context->timer.WaitUntil_ms(data->timestamp_us / 1000);
			context->lastMsgTimeMark_us = data->timestamp_us;

			ForceSeatDI_SendTopTablePosPhy(context->api, context->position);

			if (FSDI_True == ForceSeatDI_GetTopTablePosPhy(context->api, context->topTablePosition))
			{
				context->entries->push_back(
					{
						context->timer.Elapsed_ms(),
						data->accSway,
						data->accSurge,
						data->accHeave,
						context->position->sway,
						context->position->surge,
						context->position->heave,
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

	MSU_GyroPlayer_SetCsvMapping(player, 1, MSU_GPR_AccSway,  MSU_GPR_NotInverted /* no invertion*/, 1.0f);
	MSU_GyroPlayer_SetCsvMapping(player, 2, MSU_GPR_AccSurge, MSU_GPR_NotInverted /* no invertion*/, 1.0f);
	MSU_GyroPlayer_SetCsvMapping(player, 3, MSU_GPR_AccHeave, MSU_GPR_NotInverted /* no invertion*/, 1.0f);

	if (argc != 3)
	{
		std::cout << "CSV files not specified!" << std::endl;
		MSU_GyroPlayer_Delete(player);
		return -1;
	}

	std::wstring file(argv[1]);
	std::wcout << L"Loading CSV (" << file.c_str() << ")" << std::endl;

	auto result = MSU_GyroPlayer_LoadCsv(player, file.c_str(), ';', SAMPLES_INTERVAL_MS, MSU_GPR_Seconds);
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
	position.accelerationProfile = FSDI_AP_Rapid;

	CallbackContext context;
	context.api                       = ForceSeatDI_Create();
	context.position                  = &position;
	context.topTablePosition          = &topTablePosition;
	context.entries                   = &entries;
	context.lastMsgTimeMark_us        = 0;
	context.previousSampleTimeMark_us = 0;
	context.firstCall                 = true;
	memset(&context.sway,  0, sizeof(context.sway));
	memset(&context.surge, 0, sizeof(context.surge));
	memset(&context.heave, 0, sizeof(context.heave));

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
	{
		Timer timer;
		do
		{
			context.position->heave = warmupSinus(timer.Elapsed_ms(), WAKE_UP_SIGNAL_FREQ, WAKE_UP_SIGNAL_AMP_MM, 0);
			ForceSeatDI_SendTopTablePosPhy(context.api, context.position);
			std::this_thread::sleep_for(std::chrono::milliseconds(5));
		} while (timer.Elapsed_ms() < WAKE_UP_INTERVAL_MS);
	}

	// Move to center
	context.position->heave = 0;
	ForceSeatDI_SendTopTablePosPhy(context.api, context.position);
	std::this_thread::sleep_for(std::chrono::milliseconds(100));

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
	outFile << "time_s;"
			<< "given_sway_acc_m/s2;"
			<< "given_surge_acc_m/s2;"
			<< "given_heave_acc_m/s2;"
			<< "calc_sway_mm;"
			<< "calc_surge_mm;"
			<< "calc_heave_mm;" 
			<< "actual_sway_mm;"
			<< "actual_surge_mm;"
			<< "actual_heave_mm" 
			<< std::endl;

	for (auto& entry : entries)
	{
		outFile << (0.001f * entry.time_ms) << ";";
		outFile << entry.given_sway_acc     << ";";
		outFile << entry.given_surge_acc    << ";";
		outFile << entry.given_heave_acc    << ";";
		outFile << entry.calc_sway_mm       << ";";
		outFile << entry.calc_surge_mm      << ";";
		outFile << entry.calc_heave_mm      << ";";
		outFile << entry.actual_sway_mm     << ";";
		outFile << entry.actual_surge_mm    << ";";
		outFile << entry.actual_heave_mm    << std::endl;
	}

	outFile.close();

	std::cout << "Successfully completed" << std::endl;

	return 0;
}
