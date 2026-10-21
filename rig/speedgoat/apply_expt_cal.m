function apply_expt_cal(tg)
%APPLY_EXPT_CAL Push expt_cal.m into the app on the Speedgoat (loaded or running), no rebuild.
%   apply_expt_cal          connects to the default target
%   apply_expt_cal(tg)      uses an slrealtime target object (start_expt_rt passes its own)

if nargin < 1
    tg = slrealtime;
    connect(tg);
end
here = fileparts(mfilename('fullpath'));
addpath(here);
cal = expt_cal();
names = expt_tunables();
for k = 1:size(names, 1)
    if ~isempty(names{k, 2})
        setparam(tg, '', names{k, 1}, double(cal.(names{k, 2})));
    end
end
fprintf('Applied expt_cal: C diag R %s, L %s; min_fz %g N, noise floor %g N\n', ...
    mat2str(diag(cal.C1)'), mat2str(diag(cal.C2)'), cal.min_fz_N, cal.noise_floor_N);
end
