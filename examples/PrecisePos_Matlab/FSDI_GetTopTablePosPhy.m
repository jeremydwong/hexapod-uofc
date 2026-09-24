function out = FSDI_GetTopTablePosPhy(api)
    position = FSDI_ActualTopTablePositionPhysical();
    position_C = libstruct('FSDI_ActualTopTablePositionPhysical', position);

    if (0 < calllib(FSDI_Dll(),'ForceSeatDI_GetTopTablePosPhy', api, position_C))
        out = get(position_C);
    end

    clear position_C;
end
