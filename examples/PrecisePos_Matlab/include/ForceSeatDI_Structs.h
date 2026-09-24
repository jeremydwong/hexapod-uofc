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
#ifndef FORCE_SEAT_DI_STRUCTS_H
#define FORCE_SEAT_DI_STRUCTS_H

#include "ForceSeatDI_Defines.h"
#include "ForceSeatDI_ModuleErrorCodes.h"

/*
 * Possible operating states of the motion platform.
 */
typedef enum FSDI_State
{
	FSDI_State_AnyPaused                = 1 << 0, // 0b00000001
	FSDI_State_ParkingCompleted         = 1 << 1, // 0b00000010
	FSDI_State_Offline                  = 1 << 2, // 0b00000100

	FSPA_State_RefRunCompleted          = 1 << 4, // 0b00010000

	// Only one park mode is valid at given time.
	// Greater parking mode value (number) = greater priority.
	// It means that transport parking wins over normal parking
	// and normal parking wins over parking to center.
	FSDI_State_ParkModeMask             = 0xE0,   // 0b11100000
	FSDI_State_NoParking                = 0x00,   // 0b00000000
	FSDI_State_SoftParkToCenter         = 0x20,   // 0b00100000
	FSDI_State_SoftParkNormal           = 0x40,   // 0b01000000
	FSDI_State_SoftParkForTransport     = 0x60,   // 0b01100000
	FSDI_State_OperatorParkToCenter     = 0x80,   // 0b10000000
	FSDI_State_OperatorParkNormal       = 0xA0,   // 0b10100000
	FSDI_State_OperatorParkForTransport = 0xC0,   // 0b11000000
	FSDI_State_Reserved                 = 0xE0,   // 0b11100000
} FSDI_State;

/*
 * Possible parking modes for the motion platform.
 */
typedef enum FSDI_ParkMode
{
	FSDI_ParkMode_Normal       = 0,
	FSDI_ParkMode_ToCenter     = 1,
	FSDI_ParkMode_ForTransport = 2
} FSDI_ParkMode;

/*
 * Strategy for finding reachable position from request position. It is used by Inverse Kinematics module.
 */
typedef enum FSDI_Strategy
{
	FSDI_Strategy_FullMatch = 0, // Go to required position or report an error if the position is outside work envelop
	FSDI_Strategy_BestMatch = 1  // Go to closest reachable position (it scales down required position if it is outside of the work envelope)
} FSDI_Strategy;

/*
 * Definition of start/stop ramp characteristics.
 */
typedef enum FSDI_AccelerationProfile
{
	FSDI_AP_Auto      = 0, // Recommended for most applications
	FSDI_AP_Rapid     = 1,
	FSDI_AP_Balanced  = 2,
	FSDI_AP_Smoothest = 3
} FSDI_AccelerationProfile;

typedef enum FSDI_SFX_EffectType
{
	// Effect is appended to the required position before trajectory generator uses the position.
	// It means that this effect affects state of the adaptive algorithms which are used to adjust motion platform
	// operation parameters to the signal dynamics. This effect might be also less pronounced if trajectory generator
	// is configured to use long acceleration ramps.
	// It is supported only by "PS" and "QS" motion platforms.
	FSDI_SFX_EffectType_SinusLevel2 = 0,

	// Effect is appended to the output (position) of the trajectory generator. It is NOT affected by the
	// trajectory generator configuration and it does NOT affect the adaptive algorithms. Result of this effect
	// might be different depending on the actuator hardware configuration (length/pitch).
	// It is supported only by "QS" motion platforms.
	FSDI_SFX_EffectType_SinusLevel3 = 1
} FSDI_SFX_EffectType;

typedef enum FSDI_SFX_AreaFlags
{
	// Effect is generated on the actuator(s) assigned to the front-left area of the cockpit.
	FSDI_SFX_AreaFlags_FrontLeft  = 1 << 0,

	// Effect is generated on the actuator(s) assigned to the front-right area of the cockpit.
	FSDI_SFX_AreaFlags_FrontRight = 1 << 1,

	// Effect is generated on the actuator(s) assigned to the rear-left area of the cockpit.
	FSDI_SFX_AreaFlags_RearLeft   = 1 << 2,

	// Effect is generated on the actuator(s) assigned to the rear-right area of the cockpit.
	FSDI_SFX_AreaFlags_RearRight  = 1 << 3,

	// Effect is generated on auxiliary actuator, e.g. seat belt tensioner.
	FSDI_SFX_AreaFlags_Aux1       = 1 << 4,

	// Effect is generated on auxiliary actuator, e.g. seat belt tensioner.
	FSDI_SFX_AreaFlags_Aux2       = 1 << 5
} FSDI_SFX_AreaFlags;

#pragma pack(push, 1)

/*
 * This structure defines position of top frame (table) in physical units (rad, mm).
 * It uses Inverse Kinematics module and it might not be supported by all motion platforms.
 */
typedef struct FSDI_PACKED FSDI_TopTablePositionPhysical
{
	// MANDATORY: Put here sizeof(FSDI_TopTablePositionPhysical).
	FSDI_UINT8  structSize;
	FSDI_UINT32 not_used; 

	// MANDATORY: If 0, it forces motion platform pause. If 1, it allows for normal motion platform operation.
	FSDI_Bool   pause;

	// MANDATORY: Rotations define angles from the center position, translations define offsets from the center position.
	// For infinity rotation devices (e.g. PS-2ROT-150, PS-3ROT-15), the motion platform operates like clock dial - it always
	// chooses the shortest distance from current angle. I order to make a multiple rotation, following sequence should be 
	// applied (e.g. on yaw):
	// 0deg, 45deg, 90deg, 135deg, 180deg, -135def, -90deg, -45def, 0deg, 45deg, 90deg, ... 
	// NOTE: Distance between steps can be diffrent than 45deg.
	FSDI_FLOAT  roll;       // in radians, roll  < 0 = left,  roll > 0  = right
	FSDI_FLOAT  pitch;      // in radians, pitch < 0 = front, pitch > 0 = rear
	FSDI_FLOAT  yaw;        // in radians, yaw   < 0 = right, yaw > 0   = left
	FSDI_FLOAT  heave;      // in mm, heave < 0 - down, heave > 0 - top
	FSDI_FLOAT  sway;       // in mm, sway  < 0 - left, sway  > 0 - right
	FSDI_FLOAT  surge;      // in mm, surge < 0 - rear, surge > 0 - front

	// MANDATORY: Provide speed limit for motion platform operation. Actual speed is not always equal to max speed due to ramps.
	// If you don't want to manage speed, put here 65535.
	FSDI_UINT16 maxSpeed;

	// MANDATORY: One of FSDI_Strategy.
	FSDI_UINT8  strategy;  

	// MANDATORY: One of FSDI_AccelerationProfile.
	FSDI_UINT8  accelerationProfile;

} FSDI_TopTablePositionPhysical;

/*
 * This structure defines position of top frame (table) in physical units (rad, mm) by specifing transformation matrix.
 * It uses Inverse Kinematics module and it is dedicated for 6DoF motion platforms.
 * If matrix transformation is specified, the Inverse Kinematics module always uses FullMatch strategy.
 */
typedef struct FSDI_PACKED FSDI_TopTableMatrixPhysical
{
	// MANDATORY: Put here sizeof(FSDI_TopTableMatrixPhysical).
	FSDI_UINT8  structSize;
	FSDI_UINT32 not_used; 

	// MANDATORY: If 0, it forces motion platform pause. If 1, it allows for normal motion platform operation.
	FSDI_Bool   pause;

	// MANDATORY: Rotations define angles from the center position, translations define offsets from the center position.
	// NOTE: This method of control does not work for infinity rotation devices (e.g. PS-2ROT-150, PS-3ROT-15).
	//
	// 3D transformation matrix
	//
	// OFFSET (in mm):
	//   x axis = left-right movement, sway,  x < 0 - left, x > 0 - right
	//   y axis = rear-front movement, surge, y < 0 - rear, y > 0 - front
	//   z axis = down-top movement,   heave, z < 0 - down, z > 0 - top
	// 
	// ROTATION (in radians):
	//   x axis, pitch = x < 0 = front, x > 0 = rear
	//   y axis, roll = y < 0  = left,  y > 0 = right
	//   z axis, yaw  = z < 0  = right, z > 0 = left
	//
	// EXAMPLE:
	//   FSDI_FLOAT sinAX = sinf(pitch), cosAX = cosf(pitch), sinAY = sinf(roll), cosAY = cosf(roll), sinAZ = sinf(yaw), cosAZ = cosf(yaw);
	//   FSDI_FLOAT transform[4][4] =
	//   {
	//      { cosAY*cosAZ, cosAZ*sinAX*sinAY - cosAX*sinAZ, cosAX*cosAZ*sinAY + sinAX*sinAZ,  sway  },
	//      { cosAY*sinAZ, cosAX*cosAZ + sinAX*sinAY*sinAZ, -cosAZ*sinAX + cosAX*sinAY*sinAZ, surge },
	//      { -sinAY,      cosAY*sinAX,                     cosAX*cosAY,                      heave },
	//      { 0,           0,                               0,                                1     }
	//   };
	//
	FSDI_FLOAT  transformation[4][4];

	// MANDATORY: Provide speed limit for motion platform operation. Actual speed is not always equal to max speed due to ramps.
	// If you don't want to manage speed, put here 65535.
	FSDI_UINT16 maxSpeed;

	// MANDATORY: One of FSDI_AccelerationProfile.
	FSDI_UINT8  accelerationProfile;

} FSDI_TopTableMatrixPhysical;

/*
 * This structure defines position of actuators arms in logical units
 */
typedef struct FSDI_PACKED FSDI_RequiredActuatorsPositionLogical
{
	// MANDATORY: Put here sizeof(FSDI_RequiredActuatorsPositionLogical).
	FSDI_UINT8  structSize;
	FSDI_UINT32 not_used; 

	// MANDATORY: If 0, it forces motion platform pause. If 1, it allows for normal motion platform operation.
	FSDI_Bool   pause;

	// MANDATORY; 0 is minimum actuator extent (lowest angle), 65535 is maximum actuator extent (highest arm angle).
	FSDI_UINT16 actuatorPosition[FSDI_MotorsCount]; 

	// MANDATORY: Provide speed limit for motion platform operation. Actual speed is not always equal to max speed due to ramps.
	// If you don't want to manage speed, put here 65535.
	FSDI_UINT16 maxSpeed;

} FSDI_RequiredActuatorsPositionLogical;

/*
 * Actual platform status received from the controller
 */
typedef struct FSDI_PACKED FSDI_PlatformInfo
{
	// Set this to sizeof(FSDI_PlatformInfo) before calling 'get' function.
	FSDI_UINT8  structSize; 

	// Check FSDI_State for bit field explanation.
	FSDI_UINT32 state;

	FSDI_UINT8  serialNumber[FSDI_SerialNumberBytesLength];

	// Numerical error code
	FSDI_UINT8  moduleErrorCode;  

	// Index of the module that the error code refers to. If the index is 0, then it means that the error applies to the whole motion platform.
	// For example:
	// - if the index = 1, then the errorCode is related to actuator no. 1
	// - if the index = 2, then the errorCode is related to actuator no. 2
	// - if the index = 0, then the errorCode is related to whole motion platform, e.g. communication error.
	FSDI_UINT8  moduleErrorIndex; 

} FSDI_PlatformInfo;

/*
 * Actual actuators position received from the controller in logical units
 */
typedef struct FSDI_PACKED FSDI_ActualActuatorsPositionLogical
{
	// Set this to to sizeof(FSDI_ActualActuatorsPositionLogical) before calling 'get' function.
	FSDI_UINT8  structSize; 

	// Check FSDI_State for bit field explanation.
	FSDI_UINT32 state;

	FSDI_UINT16 actualMotorPosition[FSDI_MotorsCount];
	FSDI_INT32  actualMotorSpeed[FSDI_MotorsCount];

	FSDI_UINT16 requiredMotorPosition[FSDI_MotorsCount];
	FSDI_UINT16 maxAllowedMotorSpeed_obsolete[FSDI_MotorsCount]; // this field is not used anymore
} FSDI_ActualActuatorsPositionLogical;

/*
 * This structure defines position of top frame (table) in physical units (rad, mm).
 * It is calculated by forward kinematics from actual actuators position.
 */
typedef struct FSDI_PACKED FSDI_ActualTopTablePositionPhysical
{
	// Set this to to sizeof(FSDI_ActualTopTablePositionPhysical) before calling 'get' function.
	FSDI_UINT8  structSize; 

	// Check FSDI_State for bit field explanation
	FSDI_UINT32 state; 

	FSDI_FLOAT  roll;   // in radians, roll  < 0 = left,  roll > 0  = right
	FSDI_FLOAT  pitch;  // in radians, pitch < 0 = front, pitch > 0 = rear
	FSDI_FLOAT  yaw;    // in radians, yaw   < 0 = right, yaw > 0   = left
	FSDI_FLOAT  heave;  // in mm, heave < 0 - down, heave > 0 - top
	FSDI_FLOAT  sway;   // in mm, sway  < 0 - left, sway  > 0 - right
	FSDI_FLOAT  surge;  // in mm, surge < 0 - rear, surge > 0 - front
} FSDI_ActualTopTablePositionPhysical;

typedef struct FSDI_PACKED FSDI_SFX_Effect
{
	// Effect type. It is one of FSDI_SFX_EffectType.
	FSDI_UINT8 type;

	// Area where the effect should be generated. It is combination of FSDI_SFX_AreaFlags.
	FSDI_UINT16 area;

	// Frequency (Hz) of the effect, from 0 to 255. Not all effects support all frequencies.
	// - SinusL2: 0 to 100
	// - SinusL3: 0 to 100
	// - SinusL4: 0 to 100
	FSDI_UINT8 frequency;

	// Amplitude of the effect, from -1 to 1. Not all effects support full amplitudes.
	// - SinusL2: -0.12 to 0.12
	// - SinusL3: -0.12 to 0.12
	// - SinusL4: -0.12 to 0.12
	FSDI_FLOAT amplitude;

	// For future use
	FSDI_UINT8 reserved[8];
} FSDI_SFX_Effect;

/*
 * This structure defines special effects that are generated by the hardware and are independed to
 * the primary telemetry or positioning data stream. Not all devices support this feature.
 */
typedef struct FSDI_PACKED FSDI_SFX
{
	// Put here sizeof(FSDI_SFX).
	// NOTE: This field is mandatory.
	FSDI_UINT8  structSize;

	// Number of the effects specified in the below filed. From 0 to FSDI_SFX_MaxEffectsCount.
	FSDI_UINT8  effectsCount;

	// Specification of the effects
	FSDI_SFX_Effect effects[FSDI_SFX_MaxEffectsCount];
} FSDI_SFX;

/*
 * This structure defines counters (execution times) that can be used to diagnose performance issue.
 */
typedef struct FSDI_PACKED FSDI_PerformanceCounters
{
	// Set this to to sizeof(FSDI_PerformanceCounters) before calling 'get' function.
	FSDI_UINT8  structSize;

	FSDI_UINT64 testUsbConnection_us;
	FSDI_UINT64 testNetConnection_us;
	FSDI_UINT64 methodTestConnection_us;

	FSDI_UINT64 methodPark_us;
	FSDI_UINT64 methodSendTopTablePosPhy1_us;
	FSDI_UINT64 methodSendTopTablePosPhy2_us;
	FSDI_UINT64 methodSendTopTableMatrixPhy1_us;
	FSDI_UINT64 methodSendTopTableMatrixPhy2_us;
	FSDI_UINT64 methodSendActuatorsPosLog_us;
	FSDI_UINT64 methodGetPlatformInfo_us;
	FSDI_UINT64 methodGetActuatorsPosLog_us;
	FSDI_UINT64 methodGetTopTablePosPhy1_us;
	FSDI_UINT64 methodGetTopTablePosPhy2_us;

	FSDI_UINT64 apiSendStage1_us;
	FSDI_UINT64 apiSendStage2_us;
	FSDI_UINT64 apiSendStage3_us;

	FSDI_UINT64 apiGetStage1_us;
	FSDI_UINT64 apiGetStage2_us;
	FSDI_UINT64 apiGetStage3_us;
} FSDI_PerformanceCounters;

#pragma pack(pop)

#endif
