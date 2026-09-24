function out = FSDI_GetPlatformInfo(api)
    info = FSDI_PlatformInfo();
    info_C = libstruct('FSDI_PlatformInfo', info);

    if (0 < calllib(FSDI_Dll(),'ForceSeatDI_GetPlatformInfo', api, info_C))
        out = get(info_C);
    end

    clear info_C;
end
