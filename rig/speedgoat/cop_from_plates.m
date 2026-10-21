function [cop_xy, fz_total, volts_zeroed] = cop_from_plates(volts, C1, C2, origin_mm, dz_mm, tare_seq, P)
%COP_FROM_PLATES Combined centre of pressure of two force plates (MATLAB Function block).
%   volts: 12 analog inputs. P: expt_params struct (block Parameter, build-time).
%   C1, C2 (6x6), origin_mm (2x2, row k = plate k), dz_mm (1x2), tare_seq: tunable
%   CAL_* parameters (expt_cal.m, expt_tunables.m), changed on the target without a rebuild.
%   cop_xy: [x y] mm in the shared plate frame (x = sway/right, y = surge/front).
%   fz_total: total vertical force (N); CoP is NaN-free but meaningless when it is small.
%   volts_zeroed: the inputs minus their tare offsets (what the host plots).
%
%   Tare: for the first P.tare_s after the app starts, each channel's mean is accumulated
%   and the outputs are zero; from then on that mean is subtracted. The plates must be
%   empty at app start. To re-zero (plates empty), change tare_seq: retare_expt.m.
%
%   Per plate, AMTI-style: [Fx Fy Fz Mx My Mz] = C * volts, then
%     x = (-My - Fx*dz) / Fz,   y = (Mx - Fy*dz) / Fz   (local, m -> mm),
%   shifted by the plate's origin. The combined CoP is the Fz-weighted mean.
%   Sign conventions and axis directions depend on the plates and how they are
%   mounted: check against a known load (stand on a corner) before trusting it.

persistent offset n_tare last_seq
if isempty(offset)
    offset = zeros(size(volts(:)));
    n_tare = 0;
    last_seq = tare_seq;
end
if tare_seq ~= last_seq                               % re-tare requested (retare_expt)
    offset(:) = 0;
    n_tare = 0;
    last_seq = tare_seq;
end
n_need = max(round(P.tare_s / P.dt), 1);
if n_tare < n_need
    n_tare = n_tare + 1;
    offset = offset + (volts(:) - offset) / n_tare;   % running mean
    volts_zeroed = zeros(size(volts(:)));
    cop_xy = [0 0];
    fz_total = 0;
    return;
end
volts_zeroed = volts(:) - offset;

fz_total = 0;
moment = [0 0];
for k = 1:2
    if k == 1
        C = C1;
    else
        C = C2;
    end
    f = C * volts_zeroed(P.plate_channels(k, :));     % [Fx Fy Fz Mx My Mz]
    fz = f(3);
    dz = dz_mm(k) / 1000;
    if abs(fz) > 1                                    % ignore an unloaded plate
        x = 1000 * (-f(5) - f(1) * dz) / fz;
        y = 1000 * ( f(4) - f(2) * dz) / fz;
        moment = moment + fz * ([x y] + origin_mm(k, :));
        fz_total = fz_total + fz;
    end
end
if abs(fz_total) > 1
    cop_xy = moment / fz_total;
else
    cop_xy = [0 0];
end
end
