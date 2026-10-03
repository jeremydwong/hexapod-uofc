%RUN_WAYPOINTS Run Waypoints_FSDI.slx on the connected platform (or M10), then plot.
%   Preconditions: ForceSeatPM closed, platform parked, ForceSeatDI64.dll in this
%   folder (the vendor loader looks in the current folder), E-stop in reach.

here = fileparts(mfilename('fullpath'));
cd(here);
addpath(here);
addpath(fullfile(here, '..', '..', 'plugins', 'Matlab', 'Simulink'));
assert(isfile(fullfile(here, 'ForceSeatDI64.dll')), ...
    'Copy ForceSeatDI64.dll into %s first', here);
if ~isfile(fullfile(here, 'Waypoints_FSDI.slx'))
    build_waypoints_model();
end

P = waypoints_params();          % the model reads P from the base workspace
fprintf('Sequence: %d waypoints, %.0f s total. Starting.\n', size(P.W, 1), P.stop_time);
out = sim('Waypoints_FSDI');

L = out.fsdi_log;
t = L.Time;
d = squeeze(L.Data);
if size(d, 1) == 8, d = d.'; end       % samples x 8
names = {'sway', 'surge', 'heave'};
figure('Name', 'Waypoints_FSDI');
for k = 1:3
    subplot(4, 1, k);
    plot(t, d(:, k), ':', 'LineWidth', 1.5); hold on;
    plot(t, d(:, k + 3));
    ylabel([names{k} ' (mm)']); grid on;
    if k == 1, legend('command', 'reported'); end
end
subplot(4, 1, 4);
stairs(t, d(:, 7)); hold on; stairs(t, d(:, 8) * 10, 'r');
ylabel('segment / fault x10'); xlabel('time (s)'); grid on;

if any(d(:, 8))
    warning('Fault at t = %.2f s: sending stopped; the platform held its last setpoint.', ...
        t(find(d(:, 8), 1)));
end
fprintf('Max |command - reported|: %.2f mm\n', max(max(abs(d(:, 1:3) - d(:, 4:6)))));
save(fullfile(here, sprintf('waypoints_%s.mat', char(datetime('now', 'Format', 'yyyyMMdd_HHmmss')))), 't', 'd', 'P');
