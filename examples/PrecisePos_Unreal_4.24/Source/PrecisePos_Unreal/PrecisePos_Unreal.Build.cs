using UnrealBuildTool;

public class PrecisePos_Unreal : ModuleRules
{
	public PrecisePos_Unreal(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "ForceSeatDI" });

		MinFilesUsingPrecompiledHeaderOverride = 1;
		bUseUnity = true;
	}
}
