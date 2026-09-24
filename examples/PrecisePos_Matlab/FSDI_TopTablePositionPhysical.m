function out = FSDI_TopTablePositionPhysical()

out.structSize          = uint8(FSDI_Constants.Size_FSDI_TopTablePositionPhysical);
out.not_used            = 0;
out.pause               = 0;
out.roll                = 0;
out.pitch               = 0;
out.yaw                 = 0;
out.heave               = 0;
out.sway                = 0;
out.surge               = 0;
out.maxSpeed            = uint16(FSDI_Constants.Max_Speed);
out.strategy            = 0;
out.accelerationProfile = 0;

end
