function FSDI_SendActuatorsPosLog(api, position)
    calllib(FSDI_Dll(),'ForceSeatDI_SendActuatorsPosLog', api, position);
end
