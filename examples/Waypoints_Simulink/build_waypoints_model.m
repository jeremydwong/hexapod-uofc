function build_waypoints_model()
%BUILD_WAYPOINTS_MODEL Generate Waypoints_FSDI.slx: waypoint setpoints -> vendor ForceSeatDI blocks.
%   The .slx is generated, not hand-edited, so git only needs this script and
%   the .m files. Re-run after changing waypoint_setpoint_block.m; parameter
%   changes in waypoints_params.m only need run_waypoints.m.
%
%   Diagram:
%     Digital Clock ─► Setpoint (MATLAB Function) ─► ForceSeatDI_PosPhy (8 inputs)
%                        ▲                       └─► ForceSeatDI_Refresh
%     ForceSeatDI_Sway/Surge/Heave/Roll/Pitch/Yaw ┘   (reported pose feedback)
%     commanded + reported xyz, seg, fault ─► To Workspace "fsdi_log" + Scope

here = fileparts(mfilename('fullpath'));
addpath(here);
addpath(fullfile(here, '..', '..', 'plugins', 'Matlab', 'Simulink'));
lib = 'ForceSeatDI_Simulink_R2025b';
mdl = 'Waypoints_FSDI';
load_system(lib);
P = waypoints_params();
assignin('base', 'P', P);

if bdIsLoaded(mdl)
    close_system(mdl, 0);
end
new_system(mdl);

% Same settings as the vendor example: fixed 10 ms step, paced to wall clock,
% custom C code taken from the library (initialize() connects, terminate() parks).
set_param(mdl, 'SolverType', 'Fixed-step', 'Solver', 'FixedStepDiscrete', ...
    'FixedStep', '0.01', 'StopTime', 'P.stop_time', ...
    'SimUseLocalCustomCode', 'on', 'SimParseCustomCode', 'on', ...
    'EnablePacing', 'on', 'PacingRate', '1');

add_block('simulink/Sources/Digital Clock', [mdl '/Clock'], ...
    'SampleTime', '0.01', 'Position', [40 200 90 230]);

add_block('simulink/User-Defined Functions/MATLAB Function', [mdl '/Setpoint'], ...
    'Position', [250 120 450 420]);
chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [mdl '/Setpoint']);
chart.Script = fileread(fullfile(here, 'waypoint_setpoint_block.m'));
param = chart.find('-isa', 'Stateflow.Data', 'Name', 'P');
param.Scope = 'Parameter';

% Reported pose getters feed Setpoint inputs 2..7 (input 1 is the clock).
getters = {'Sway', 'Surge', 'Heave', 'Roll', 'Pitch', 'Yaw'};
for k = 1:numel(getters)
    name = ['Get' getters{k}];
    add_block([lib '/ForceSeatDI_' getters{k}], [mdl '/' name], ...
        'Position', [40 260 + 50*k 160 290 + 50*k]);
    add_line(mdl, [name '/1'], sprintf('Setpoint/%d', k + 1), 'autorouting', 'on');
end
add_line(mdl, 'Clock/1', 'Setpoint/1', 'autorouting', 'on');

% Setpoint outputs 1..8 -> PosPhy (yaw, pitch, roll, heave, sway, surge, strategy, enable),
% the argument order of SetPosPhy in plugins/Matlab/Simulink/include/ForceSeatDI_Simulink.h.
add_block([lib '/ForceSeatDI_PosPhy'], [mdl '/PosPhy'], 'Position', [600 100 800 360]);
for k = 1:8
    add_line(mdl, sprintf('Setpoint/%d', k), sprintf('PosPhy/%d', k), 'autorouting', 'on');
end
add_block([lib '/ForceSeatDI_Refresh'], [mdl '/Refresh'], 'Position', [600 400 800 440]);
add_line(mdl, 'Setpoint/9', 'Refresh/1', 'autorouting', 'on');

% Log: commanded sway/surge/heave, reported sway/surge/heave, segment, fault.
add_block('simulink/Signal Routing/Mux', [mdl '/LogMux'], 'Inputs', '8', ...
    'Position', [900 460 910 640]);
sources = {'Setpoint/5', 'Setpoint/6', 'Setpoint/4', 'GetSway/1', 'GetSurge/1', ...
           'GetHeave/1', 'Setpoint/10', 'Setpoint/11'};
for k = 1:numel(sources)
    add_line(mdl, sources{k}, sprintf('LogMux/%d', k), 'autorouting', 'on');
end
add_block('simulink/Sinks/To Workspace', [mdl '/Log'], 'VariableName', 'fsdi_log', ...
    'SaveFormat', 'Timeseries', 'Position', [1000 520 1080 550]);
add_line(mdl, 'LogMux/1', 'Log/1', 'autorouting', 'on');
add_block('simulink/Sinks/Scope', [mdl '/Scope'], 'Position', [1000 600 1040 640]);
add_line(mdl, 'LogMux/1', 'Scope/1', 'autorouting', 'on');

save_system(mdl, fullfile(here, [mdl '.slx']));
open_system(mdl);
fprintf('Built %s. Run run_waypoints.m to drive the platform.\n', fullfile(here, [mdl '.slx']));
end
