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

#include "PrecisePos_UnrealPawn.h"
#include "PrecisePos_Unreal.h"
#include "Math/UnrealMathUtility.h"
#include "IForceSeatDI.h"

namespace
{
	// Maximum speed that platform can move with
	const int PLATFORM_MAX_SPEED = 25000;

	// Heave maximum value that is available in the game
	const float DRAWING_HEAVE_MAX = 80.f;

	// Heave change step
	const float DRAWING_HEAVE_STEP = 4.f;

	// Maximum value of pitch angle that is available in the game
	const float DRAWING_PITCH_MAX = 0.2;

	// Pitch change step
	const float DRAWING_PITCH_STEP = 0.01f;

	// Maximum value of roll angle that is available in the game
	const float DRAWING_ROLL_MAX = 0.2f;

	// Pitch change step
	const float DRAWING_ROLL_STEP = 0.01f;
}

APrecisePos_UnrealPawn::APrecisePos_UnrealPawn()
	: CurrentDrawingHeave(0)
	, CurrentDrawingPitch(0)
	, CurrentDrawingRoll(0)
	, IsPlatformConnected(false)
	, IsLicenseValid(false)
{
	PrimaryActorTick.bCanEverTick = true;

	// Create platform's board subobject
	Board = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Board0"));
	Board->BodyInstance.SetCollisionProfileName(UCollisionProfile::PhysicsActor_ProfileName);
	Board->SetSimulatePhysics(false);
	Board->SetNotifyRigidBodyCollision(true);

	// Create platform's base subobject
	Base = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Base0"));
	Base->BodyInstance.SetCollisionProfileName(UCollisionProfile::PhysicsActor_ProfileName);
	Base->SetSimulatePhysics(false);
	Base->SetNotifyRigidBodyCollision(true);

	// Create platform's shaft subobject
	Shaft = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Shaft0"));
	Shaft->BodyInstance.SetCollisionProfileName(UCollisionProfile::PhysicsActor_ProfileName);
	Shaft->SetSimulatePhysics(false);
	Shaft->SetNotifyRigidBodyCollision(true);

	// Create shaft's head subobject
	ShaftHead = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ShaftHead0"));
	ShaftHead->BodyInstance.SetCollisionProfileName(UCollisionProfile::PhysicsActor_ProfileName);
	ShaftHead->SetSimulatePhysics(false);
	ShaftHead->SetNotifyRigidBodyCollision(true);

	// Create root subobject
	Root = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Root0"));
	Root->BodyInstance.SetCollisionProfileName(UCollisionProfile::PhysicsActor_ProfileName);
	Root->SetSimulatePhysics(false);
	Root->SetNotifyRigidBodyCollision(true);

	RootComponent = Root;

	// ForceSeatDI - BEGIN
	// Initialize platform position structure
	memset(&PlatformPosition, 0, sizeof(PlatformPosition));
	PlatformPosition.structSize = sizeof(FSDI_TopTablePositionPhysical);

	// The demo program is able to provide pause, position and speed limit
	PlatformPosition.maxSpeed = PLATFORM_MAX_SPEED;
	PlatformPosition.maxSpeed = 65535;
	PlatformPosition.pause    = FSDI_False;
	PlatformPosition.strategy = FSDI_Strategy_BestMatch;
	// ForceSeatDI - END
}

void APrecisePos_UnrealPawn::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	// Update board's origin transformation (in game) with current heave, pitch and roll values
	FVector BoardLocation = BoardOriginTransform.GetLocation();
	FQuat BoardRotation = BoardOriginTransform.GetRotation();
	BoardLocation.Z += CurrentDrawingHeave;
	BoardRotation.X += CurrentDrawingPitch;
	BoardRotation.Y += CurrentDrawingRoll;

	// Set calculated transformation for board subobject
	Board->SetRelativeLocationAndRotation(BoardLocation, BoardRotation);

	// Update shaft's origin transformation  (in game) with current heave value
	FVector ShaftLocation = ShaftOriginTransform.GetLocation();
	ShaftLocation.Z += CurrentDrawingHeave;

	// Set calculated transformation for shaft subobject
	Shaft->SetRelativeLocationAndRotation(ShaftLocation, ShaftOriginTransform.GetRotation());

	// Update shaft's head origin transformation  (in game) with current heave value
	FVector ShaftHeadLocation = ShaftHeadOriginTransform.GetLocation();
	ShaftHeadLocation.Z += CurrentDrawingHeave;

	// Set calculated transformation for shaft's head subobject
	ShaftHead->SetRelativeLocationAndRotation(ShaftHeadLocation, ShaftHeadOriginTransform.GetRotation());

	// ForceSeatDI - BEGIN
	SendCoordinatesToPlatform();
	// ForceSeatDI - END
}

void APrecisePos_UnrealPawn::SetupPlayerInputComponent(class UInputComponent* InputComponent)
{
	// Bind control axis' to callback functions
	InputComponent->BindAxis("MoveUp", this, &APrecisePos_UnrealPawn::MoveUp);
	InputComponent->BindAxis("RotateForward", this, &APrecisePos_UnrealPawn::RotateForward);
	InputComponent->BindAxis("RotateRight", this, &APrecisePos_UnrealPawn::RotateRight);

	Super::SetupPlayerInputComponent(InputComponent);
}

void APrecisePos_UnrealPawn::BeginPlay()
{
	Super::BeginPlay();

	// Get origin transformations for movable subobjects
	BoardOriginTransform = Board->GetRelativeTransform();
	ShaftOriginTransform = Shaft->GetRelativeTransform();
	ShaftHeadOriginTransform = ShaftHead->GetRelativeTransform();

	// ForceSeatDI - BEGIN
	if (!IForceSeatDI::Get().ConnectToUsbDevice(nullptr, nullptr))
	{
		return;
	}

	IsPlatformConnected = true;

	FSDI_Bool isValid = FSDI_False;
	IForceSeatDI::Get().GetLicenseStatus(&isValid);

	if (FSDI_False == isValid)
	{
		return;
	}

	IsLicenseValid = true;

	SendCoordinatesToPlatform();
	// ForceSeatMI - END
}

void APrecisePos_UnrealPawn::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	Super::EndPlay(EndPlayReason);

	// ForceSeatDI - BEGIN
	IForceSeatDI::Get().Park(FSDI_ParkMode_Normal);
	// ForceSeatDI - END
}

void APrecisePos_UnrealPawn::UpdateValue(float& value, float input, float step, float min, float max)
{
	if (0 < input)
	{
		value = FMath::Clamp<float>(value + step, min, max);
	}
	else if (0 > input)
	{
		value = FMath::Clamp<float>(value - step, min, max);
	}
	else if (value > 0)
	{
		value = FMath::Clamp<float>(value - step, 0, max);
	}
	else if (value < 0)
	{
		value = FMath::Clamp<float>(value + step, min, 0);
	}
}

void APrecisePos_UnrealPawn::SendCoordinatesToPlatform()
{
	// ForceSeatMI - BEGIN
	PlatformPosition.pause = FSDI_False;
	PlatformPosition.roll  = CurrentDrawingRoll;
	PlatformPosition.pitch = -CurrentDrawingPitch;
	PlatformPosition.heave = CurrentDrawingHeave;

	IForceSeatDI::Get().SendTopTablePosPhy(&PlatformPosition);
	// ForceSeatMI - END
}

void APrecisePos_UnrealPawn::MoveUp(float Val)
{
	// Update drawing heave value with specified step
	UpdateValue(CurrentDrawingHeave, Val, DRAWING_HEAVE_STEP, 0, DRAWING_HEAVE_MAX);
}

void APrecisePos_UnrealPawn::RotateForward(float Val)
{
	// Update drawing pitch value with specified step
	UpdateValue(CurrentDrawingPitch, Val, DRAWING_PITCH_STEP, -DRAWING_PITCH_MAX, DRAWING_PITCH_MAX);
}

void APrecisePos_UnrealPawn::RotateRight(float Val)
{
	// Update drawing roll value with specified step
	UpdateValue(CurrentDrawingRoll, Val, DRAWING_ROLL_STEP, -DRAWING_ROLL_MAX, DRAWING_ROLL_MAX);
}
