function out = FSDI_ConnectToNetworkDevice(api, ipAddress)
    out = calllib(FSDI_Dll(),'ForceSeatDI_ConnectToNetworkDevice', api, ipAddress);
end
