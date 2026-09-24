#include "ForceSeatDI_Simulink.h"
#include "ForceSeatDI_Functions.h"

#include <stdio.h>
#include <stdlib.h>
#include <time.h>

void logToFile(const char *message)
{
	FILE *file = fopen("fsdi_simulink_log.txt", "a");
	if (NULL == file)
	{
		return;
	}

	time_t now = time(NULL);
	struct tm* t = localtime(&now);

	fprintf(file, "%04d-%02d-%02d_%02d:%02d:%02d : %s\n",
			t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
			t->tm_hour, t->tm_min, t->tm_sec, message);

	fclose(file);
}

FSDI_Handle                         g_handle = 0;
FSDI_TopTablePositionPhysical       g_positionPhy;
FSDI_ActualActuatorsPositionLogical g_actualActuatorsPosition;
FSDI_ActualTopTablePositionPhysical g_topTablePosition;
FSDI_PlatformInfo                   g_platformInfo;

void initialize()
{
	logToFile("Initialize has been called");
	
	g_handle = ForceSeatDI_Create();

	if (g_handle)
	{
		logToFile("Api has been created");

		memset(&g_positionPhy, 0, sizeof(g_positionPhy));
		g_positionPhy.structSize = sizeof(FSDI_TopTablePositionPhysical);
		g_positionPhy.maxSpeed   = 65535;
		g_positionPhy.pause      = FSDI_False;
		g_positionPhy.strategy   = FSDI_Strategy_BestMatch;

		memset(&g_actualActuatorsPosition, 0, sizeof(g_actualActuatorsPosition));
		g_actualActuatorsPosition.structSize = sizeof(FSDI_ActualActuatorsPositionLogical);

		memset(&g_topTablePosition, 0, sizeof(g_topTablePosition));
		g_topTablePosition.structSize = sizeof(FSDI_ActualTopTablePositionPhysical);

		memset(&g_platformInfo, 0, sizeof(g_platformInfo));
		g_platformInfo.structSize = sizeof(FSDI_PlatformInfo);
	}
}

void terminate()
{
	logToFile("Terminate has been called");

	if(0 != g_handle)
	{
		ForceSeatDI_Park(g_handle, FSDI_ParkMode_Normal);
		ForceSeatDI_Delete(g_handle);
		g_handle = 0;
	}
}

void Refresh(int enable)
{
	if (0 < enable)
	{
		ForceSeatDI_GetActuatorsPosLog(g_handle, &g_actualActuatorsPosition);
		ForceSeatDI_GetPlatformInfo(g_handle,    &g_platformInfo);
		ForceSeatDI_GetTopTablePosPhy(g_handle,  &g_topTablePosition);
	}
	else
	{
		logToFile("Refresh cannot be called because enabled is 0!");
	}
}

void SetPosPhy(double yaw_rad, double pitch_rad, double roll_rad, double heave_mm, double sway_mm, double surge_mm, int strategy, int enable)
{
	if (0 >= enable)
	{
		logToFile("Cannot send position as enabled is 0!");
		return;
	}

	g_positionPhy.strategy = (1 == strategy) ? FSDI_Strategy_BestMatch : FSDI_Strategy_FullMatch;
	g_positionPhy.roll     = roll_rad;
	g_positionPhy.pitch    = pitch_rad;
	g_positionPhy.yaw      = yaw_rad;
	g_positionPhy.heave    = heave_mm;
	g_positionPhy.sway     = sway_mm; 
	g_positionPhy.surge    = surge_mm;

	ForceSeatDI_SendTopTablePosPhy(g_handle, &g_positionPhy);

	Refresh(enable);
}

double GetYaw_rad()
{
	return g_topTablePosition.yaw;
}

double GetPitch_rad()
{
	return g_topTablePosition.pitch;
}

double GetRoll_rad()
{
	return g_topTablePosition.roll;
}

double GetHeave_mm()
{
	return g_topTablePosition.heave;
}

double GetSway_mm()
{
	return g_topTablePosition.sway;
}

double GetSurge_mm()
{
	return g_topTablePosition.surge;
}

int BestMatchStrategy()
{
	return FSDI_Strategy_BestMatch;
}

int FullMatchStrategy()
{
	return FSDI_Strategy_FullMatch;
}
