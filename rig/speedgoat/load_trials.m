function [TT, n] = load_trials(csv_path, P)
%LOAD_TRIALS Read a trial table CSV into the 500 x 8 matrix that fsm_expt takes.
%   [TT, n] = load_trials('trials_example.csv', expt_params())
%   For desktop tests (test_fsm_expt.m). On the Speedgoat the host sends the table
%   (hexapod-expt-run), and host_rx.m applies the same checks.
%   Columns (header names must match; order does not matter):
%     random_s                   wait at home before the perturbation starts (s)
%     axis                       1 = surge (+ front), 2 = sway (+ right)
%     distance_mm                signed perturbation distance from home (mm)
%     peak_speed_mm_s            peak speed of the smoothstep move (mm/s)
%     thresh_seconds_cop_stable  CoP must stay stable this long before returning (s)
%     cop_radius_mm              "near centre": |CoP - centre| below this (mm)
%     cop_sd_mm                  "low variability": CoP running SD below this (mm)
%     max_wait_s                 optional: return anyway after this long (s); 0 = never

N_MAX = 500;
tbl = readtable(csv_path);
cols = {'random_s', 'axis', 'distance_mm', 'peak_speed_mm_s', ...
        'thresh_seconds_cop_stable', 'cop_radius_mm', 'cop_sd_mm', 'max_wait_s'};
if ~ismember('max_wait_s', tbl.Properties.VariableNames)
    tbl.max_wait_s = zeros(height(tbl), 1);
end
missing = setdiff(cols, tbl.Properties.VariableNames);
assert(isempty(missing), 'Trial table %s is missing columns: %s', csv_path, strjoin(missing, ', '));
n = height(tbl);
assert(n >= 1 && n <= N_MAX, 'Trial table needs 1..%d rows, has %d', N_MAX, n);
TT = zeros(N_MAX, 8);
for j = 1:8
    TT(1:n, j) = tbl.(cols{j});
end
for k = 1:n
    ax = TT(k, 2);
    assert(ax == 1 || ax == 2, 'Trial %d: axis must be 1 (surge) or 2 (sway)', k);
    lim = P.limits_mm(ax, :);
    assert(TT(k, 3) >= lim(1) && TT(k, 3) <= lim(2), ...
        'Trial %d: %g mm on axis %d is outside the safe range [%g, %g]', k, TT(k, 3), ax, lim(1), lim(2));
    assert(TT(k, 4) > 0 && TT(k, 4) <= P.max_peak_speed_mm_s, 'Trial %d: bad peak_speed_mm_s', k);
    assert(TT(k, 1) >= 0 && TT(k, 5) > 0 && TT(k, 8) >= 0, 'Trial %d: bad times', k);
end
end
