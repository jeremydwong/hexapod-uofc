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

#include "ForceSeatDI_Structs.h"
#include "GameFramework/Pawn.h"
#include "PrecisePos_UnrealPawn.generated.h"

class IForceSeatDI;

UCLASS()
class PRECISEPOS_UNREAL_API APrecisePos_UnrealPawn : public APawn
{
	GENERATED_BODY()
public:
	APrecisePos_UnrealPawn();

	/** Moves platform's board up */
	void MoveUp(float Val);

	/** Rotates platform's board forward and backward */
	void RotateForward(float Val);
	
	/** Rotates platform's board left and right */
	void RotateRight(float Val);

public:
	/** Called every frame */
	virtual void Tick(float DeltaTime) override;

	/** Used to configure input */
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

	/** Returns mesh subobject that represents platform's board */
	FORCEINLINE class UStaticMeshComponent* GetBoard() const { return Board; }

	/** Returns mesh subobject that represents base of the platform */
	FORCEINLINE class UStaticMeshComponent* GetBase() const { return Base; }

	/** Returns mesh subobject that represents platform's shaft */
	FORCEINLINE class UStaticMeshComponent* GetShaft() const { return Shaft; }

	/** Returns mesh subobject that represents shaft's head */
	FORCEINLINE class UStaticMeshComponent* GetShaftHead() const { return ShaftHead; }

	/** Returns root subobject */
	FORCEINLINE class UStaticMeshComponent* GetRoot() const { return Root; }

protected:
	/** Called when play begins */
	virtual void BeginPlay() override;

	/** Called whenever actor is removed from level */
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	/** Updates specified value */
	void UpdateValue(float& value, float input, float step, float min, float max);

	/** Sends logical coordinates to the platform */
	void SendCoordinatesToPlatform();

private:
	/** Platform's board component */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = Mesh, meta = (AllowPrivateAccess = "true"))
	class UStaticMeshComponent* Board;

	/** Platform's base component */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = Mesh, meta = (AllowPrivateAccess = "true"))
	class UStaticMeshComponent* Base;

	/** Platform's shaft component */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = Mesh, meta = (AllowPrivateAccess = "true"))
	class UStaticMeshComponent* Shaft;

	/** Shaft's head component */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = Mesh, meta = (AllowPrivateAccess = "true"))
	class UStaticMeshComponent* ShaftHead;

	/** Root component */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = Mesh, meta = (AllowPrivateAccess = "true"))
	class UStaticMeshComponent* Root;

	/** Current platform's heave in game */
	float CurrentDrawingHeave;

	/** Current platform's pitch in game */
	float CurrentDrawingPitch;

	/** Current platform's roll in game */
	float CurrentDrawingRoll;

	/** Transformation that represents origin position of platform's board component in game coordinates */
	FTransform BoardOriginTransform;
	
	/** Transformation that represents origin position of platform's shaft component in game coordinates */
	FTransform ShaftOriginTransform;

	/** Transformation that represents origin position of shaft's head component in game coordinates */
	FTransform ShaftHeadOriginTransform;

	/** Position in logical coordinates that will be send to the platform */
	FSDI_TopTablePositionPhysical PlatformPosition;

	/** Tels if motion platform is recognized and connected */
	bool IsPlatformConnected;

	/** Tells if motion platform has license activated */
	bool IsLicenseValid;
};
