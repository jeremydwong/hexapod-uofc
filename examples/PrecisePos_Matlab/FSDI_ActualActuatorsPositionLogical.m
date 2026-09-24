function out = FSDI_ActualActuatorsPositionLogical()

out.structSize                    = uint8(FSDI_Constants.Size_FSDI_ActualActuatorsPositionLogical);
out.state                         = 0;
out.actualMotorPosition           = [0, 0, 0, 0, 0, 0];
out.actualMotorSpeed              = [0, 0, 0, 0, 0, 0];
out.requiredMotorPosition         = [0, 0, 0, 0, 0, 0];
out.maxAllowedMotorSpeed_obsolete = [0, 0, 0, 0, 0, 0];

end
