function out = FSDI_GetLicenseStatus(api)
    status = libpointer('int8Ptr', zeros(1, 1, 'int8'));

    calllib(FSDI_Dll(),'ForceSeatDI_GetLicenseStatus', api, status);
    
    out = status.Value;
end
