function out = FSDI_PlatformInfo()

out.structSize                   = uint8(FSDI_Constants.Size_FSDI_PlatformInfo);
out.state                        = 0;
out.serialNumber                 = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ];
out.moduleErrorCode              = 0;
out.moduleErrorIndex             = 0;

end
