using UnrealBuildTool;
using System.Collections.Generic;

public class PrecisePos_UnrealTarget : TargetRules
{
	public PrecisePos_UnrealTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		ExtraModuleNames.AddRange( new string[] { "PrecisePos_Unreal" } );
	}
}
