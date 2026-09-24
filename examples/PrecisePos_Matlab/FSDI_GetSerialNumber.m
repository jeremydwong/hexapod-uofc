function out = FSDI_GetSerialNumber(api)
    out = '';
    serialNumber = libpointer('int8Ptr', zeros(uint32(FSDI_Constants.Size_SerialNumber), 1, 'int8'));

    if 0 < calllib(FSDI_Dll(),'ForceSeatDI_GetSerialNumber', api, serialNumber)
        out = convertCharsToStrings(char(serialNumber.Value));
    end
end
