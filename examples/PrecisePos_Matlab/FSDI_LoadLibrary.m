function FSDI_LoadLibrary()
    if not(libisloaded(FSDI_Dll()))
        loadlibrary(append('bin\', FSDI_Dll()), 'include/ForceSeatDI_Functions.h')
    end
end
