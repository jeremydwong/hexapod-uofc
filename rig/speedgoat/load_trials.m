function T = load_trials(csv_path, max_trials)
%LOAD_TRIALS Read a trial table CSV into a fixed-size struct for the FSM_EXPT block.
%   Columns (header names must match; order does not matter):
%     trial                      trial number (informational)
%     random_s                   wait at home before the perturbation starts (s)
%     axis                       1 = surge (+ front), 2 = sway (+ right)
%     distance_mm                signed perturbation distance from home (mm)
%     peak_speed_mm_s            peak speed of the smoothstep move (mm/s)
%     thresh_seconds_cop_stable  CoP must stay stable this long before returning (s)
%     cop_radius_mm              "near centre": |CoP - centre| below this (mm)
%     cop_sd_mm                  "low variability": CoP running SD below this (mm)
%
%   Arrays are padded to max_trials so the generated code has fixed sizes; T.n is the
%   number of real trials. Also checks every target against the safe excursion limits.

if nargin < 2, max_trials = 500; end
tbl = readtable(csv_path);
need = {'random_s', 'axis', 'distance_mm', 'peak_speed_mm_s', ...
        'thresh_seconds_cop_stable', 'cop_radius_mm', 'cop_sd_mm'};
missing = setdiff(need, tbl.Properties.VariableNames);
assert(isempty(missing), 'Trial table %s is missing columns: %s', csv_path, strjoin(missing, ', '));
n = height(tbl);
assert(n >= 1 && n <= max_trials, 'Trial table needs 1..%d rows, has %d', max_trials, n);
assert(all(ismember(tbl.axis, [1 2])), 'axis must be 1 (surge) or 2 (sway)');
assert(all(tbl.peak_speed_mm_s > 0), 'peak_speed_mm_s must be positive');
assert(all(tbl.random_s >= 0) && all(tbl.thresh_seconds_cop_stable > 0), 'times must be positive');

% Safe single-axis targets at home height: measured limits on the M10 imitator
% (surge -306 / +273, sway +/-266 mm) minus a 25 mm margin.
limits = [-281 248; -241 241];  % rows: surge, sway
for k = 1:n
    lim = limits(tbl.axis(k), :);
    assert(tbl.distance_mm(k) >= lim(1) && tbl.distance_mm(k) <= lim(2), ...
        'Trial %d: %g mm on axis %d is outside the safe range [%g, %g]', ...
        k, tbl.distance_mm(k), tbl.axis(k), lim(1), lim(2));
end

pad = @(x) [x(:); zeros(max_trials - n, 1)];
T.n = n;
T.random_s = pad(tbl.random_s);
T.axis = pad(tbl.axis);
T.distance_mm = pad(tbl.distance_mm);
T.peak_speed_mm_s = pad(tbl.peak_speed_mm_s);
T.thresh_seconds_cop_stable = pad(tbl.thresh_seconds_cop_stable);
T.cop_radius_mm = pad(tbl.cop_radius_mm);
T.cop_sd_mm = pad(tbl.cop_sd_mm);
end
