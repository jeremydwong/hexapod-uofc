function FSDI_Park(api, parkMode)
    calllib(FSDI_Dll(),'ForceSeatDI_Park', api, parkMode);
end
