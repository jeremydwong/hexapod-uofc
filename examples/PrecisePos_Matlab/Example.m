position = FSDI_TopTablePositionPhysical();
maxRoll  = 10;
iterator = 0;

FSDI_LoadLibrary();

api = FSDI_Create();

%serialNumber = 'xxxxxxxxxxxxxxxxxxxxxxxx';
%serialNumberPtr = libpointer('voidPtr',[uint16(serialNumber) 0]);

serialNumberPtr = libpointer;
connected = FSDI_ConnectToUsbDevice(api, libpointer, serialNumberPtr);

%connected = FSDI_ConnectToNetworkDevice(api, '10.1.1.75');

if 0 < connected
    if 0 < FSDI_GetLicenseStatus(api)
        if 0 < FSDI_TestConnection(api)

            disp(FSDI_GetSerialNumber(api));

            if 0 < FSDI_GetLicenseStatus(api)       
                while iterator < 2000
                    position.roll = sin(iterator * 3.1415 / 180) * maxRoll * 3.1415 / 180;

                    FSDI_SendTopTablePosPhy(api, position);

                    iterator = iterator + 0.5;

                    actuatorsPosition = FSDI_GetActuatorsPosLog(api);
                    topTablePositionPhysical = FSDI_GetTopTablePosPhy(api);
                    platformInfo = FSDI_GetPlatformInfo(api);
                    
                    errorCode = FSDI_GetRecentErrorCode(api);

                    % NOTE: Add pause/sleep here to keep constant rate (100~250Hz) of FSDI_SendTopTablePosPhy calls
                    % https://www.mathworks.com/help/robotics/ug/fixed-rate-execution.html
                end
            end
        end
    end
end

FSDI_Park(api, 0);
FSDI_Delete(api);

clear api;

FSDI_UnloadLibrary();
