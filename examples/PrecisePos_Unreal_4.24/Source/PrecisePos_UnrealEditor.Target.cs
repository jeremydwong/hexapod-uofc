using UnrealBuildTool;
using System.Collections.Generic;

public class PrecisePos_UnrealEditorTarget : TargetRules
{
	public PrecisePos_UnrealEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		ExtraModuleNames.AddRange( new string[] { "PrecisePos_Unreal" } );
	}
}
