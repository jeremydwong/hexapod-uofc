function cal = expt_cal()
%EXPT_CAL Tunable values for expt_rt: edit here, NO rebuild needed.
%   start_expt_rt pushes these onto the target after every load; apply_expt_cal pushes them
%   into the running app. The build only takes their sizes (expt_tunables.m), so editing
%   values never makes the build stale. Build-time settings stay in expt_params.m.

% Force plates: [Fx Fy Fz Mx My Mz] (N, N*m) = C * volts. Scale factors from the lab
% (2026-10-21), per volt at the amplifiers' +-5 V output (halve them for +-10 V).
% Fz sign NOT yet checked: press on a plate; total Fz should go positive.
gains = diag([500 500 1000 150 100 75]);
cal.C1 = gains;                   % RIGHT plate, AI 1-6 (Fy confirmed by a push, 2026-10-20)
cal.C2 = gains;                   % LEFT plate, AI 7-12
% Plates: 200 x 200 mm, 50 mm gap, centred on the top frame (lab, 2026-10-21): centres at x = +-125 mm.
cal.origin_mm = [125 0; -125 0];  % plate centres, rows = plate 1, 2 (x = sway/right, y = surge/front)
cal.dz_mm = [0 0];                % depth of each plate's measurement origin below its surface

% CoP gates (fsm_expt.m)
cal.min_fz_N = 200;               % CoP gates need at least this total vertical force (someone standing)
cal.noise_floor_N = 50;           % below this: plates empty, CoP gates are overridden. PLACEHOLDER:
                                  % set from the zeroed empty-plate Fz noise
end
