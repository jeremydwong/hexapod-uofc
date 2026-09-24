function out = FSDI_TestConnection(api)
    isConnected = libpointer('int8Ptr', zeros(1, 1, 'int8'));

    calllib(FSDI_Dll(),'ForceSeatDI_TestConnection', api, isConnected);

    out = isConnected.Value;
end
