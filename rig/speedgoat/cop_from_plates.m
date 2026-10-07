function [cop_xy, fz_total] = cop_from_plates(volts, P)
%COP_FROM_PLATES Combined centre of pressure of two force plates (MATLAB Function block).
%   volts: 12 analog inputs. P: expt_params struct (block Parameter).
%   cop_xy: [x y] mm in the shared plate frame (x = sway/right, y = surge/front).
%   fz_total: total vertical force (N); CoP is NaN-free but meaningless when it is small.
%
%   Per plate, AMTI-style: [Fx Fy Fz Mx My Mz] = C * volts, then
%     x = (-My - Fx*dz) / Fz,   y = (Mx - Fy*dz) / Fz   (local, m -> mm),
%   shifted by the plate's origin. The combined CoP is the Fz-weighted mean.
%   Sign conventions and axis directions depend on the plates and how they are
%   mounted: check against a known load (stand on a corner) before trusting it.

fz_total = 0;
moment = [0 0];
for k = 1:2
    plate = P.plate(k);
    f = plate.C * volts(plate.channels(:));          % [Fx Fy Fz Mx My Mz]
    fz = f(3);
    dz = plate.dz_mm / 1000;
    if abs(fz) > 1                                    % ignore an unloaded plate
        x = 1000 * (-f(5) - f(1) * dz) / fz;
        y = 1000 * ( f(4) - f(2) * dz) / fz;
        moment = moment + fz * ([x y] + plate.origin_mm);
        fz_total = fz_total + fz;
    end
end
if abs(fz_total) > 1
    cop_xy = moment / fz_total;
else
    cop_xy = [0 0];
end
end
