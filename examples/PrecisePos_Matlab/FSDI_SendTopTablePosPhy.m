function FSDI_SendTopTablePosPhy(api, position)
    calllib(FSDI_Dll(),'ForceSeatDI_SendTopTablePosPhy', api, position);
end
