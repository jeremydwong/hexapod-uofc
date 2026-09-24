function out = FSDI_GetActuatorsPosLog(api)
    position = FSDI_ActualActuatorsPositionLogical();
    position_C = libstruct('FSDI_ActualActuatorsPositionLogical', position);

    if (0 < calllib(FSDI_Dll(),'ForceSeatDI_GetActuatorsPosLog', api, position_C))
        out = get(position_C);
    end

    clear position_C;
end
