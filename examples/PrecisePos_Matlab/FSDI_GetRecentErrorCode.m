function out = FSDI_GetRecentErrorCode(api)
    out = calllib(FSDI_Dll(),'ForceSeatDI_GetRecentErrorCode', api);
end
