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

using UnrealBuildTool;

public class ForceSeatDI : ModuleRules
{
	public ForceSeatDI(ReadOnlyTargetRules Target) : base(Target)
	{
		PublicDefinitions.Add("NO_IMPORT_FORCESEAT_DI");
		PublicDependencyModuleNames.AddRange(new string[] { "Core" });
		PrivateDependencyModuleNames.AddRange(new string[] { "CoreUObject", "Engine", "PhysXVehicles" } );
		DynamicallyLoadedModuleNames.AddRange(new string[] {});

		PublicDependencyModuleNames.Add("PhysXVehicles");
		PrivateDependencyModuleNames.Add("PhysXVehicles");

		PrivatePCHHeaderFile = "Public/ForceSeatDI_PCH.h";
	}
}
