function api = FSDI_Create()
    FSDI_LoadLibrary();
    api = calllib(FSDI_Dll(), 'ForceSeatDI_Create');
end
