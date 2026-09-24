function out = FSDI_ConnectToUsbDevice(api, name, serialNumber)
    out = calllib(FSDI_Dll(),'ForceSeatDI_ConnectToUsbDevice', api, name, serialNumber);
end
