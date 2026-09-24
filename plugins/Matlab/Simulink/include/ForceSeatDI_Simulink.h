#ifndef FORCE_SEAT_DI_SIMULINK_H
#define FORCE_SEAT_DI_SIMULINK_H

void SetPosPhy(double yaw_rad, double pitch_rad, double roll_rad, double heave_mm, double sway_mm, double surge_mm, int strategy, int enable);
void Refresh(int enable);

double GetYaw_rad();
double GetPitch_rad();
double GetRoll_rad();
double GetHeave_mm();
double GetSway_mm();
double GetSurge_mm();

int BestMatchStrategy();
int FullMatchStrategy();

void initialize();
void terminate();

#endif
