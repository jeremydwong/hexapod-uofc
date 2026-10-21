function names = expt_tunables()
%EXPT_TUNABLES Create the tunable CAL_* parameters in the base workspace for the build.
%   Each is a Simulink.Parameter (ExportedGlobal, so tunable on the target by name) read by a
%   Constant block. Values come from expt_cal.m; only their sizes matter to the build, because
%   start_expt_rt / apply_expt_cal overwrite them on the target. Returns {name, cal field}.

names = {'CAL_C1', 'C1'; 'CAL_C2', 'C2'; 'CAL_ORIGIN_MM', 'origin_mm'; 'CAL_DZ_MM', 'dz_mm'; ...
         'CAL_MIN_FZ_N', 'min_fz_N'; 'CAL_NOISE_FLOOR_N', 'noise_floor_N'; 'CAL_TARE_SEQ', ''};
cal = expt_cal();
for k = 1:size(names, 1)
    if isempty(names{k, 2})
        value = 0;                % CAL_TARE_SEQ: change it to re-zero the load cells (retare_expt)
    else
        value = cal.(names{k, 2});
    end
    p = Simulink.Parameter(double(value));
    p.CoderInfo.StorageClass = 'ExportedGlobal';
    assignin('base', names{k, 1}, p);
end
end
