function build_expt_rt()
%BUILD_EXPT_RT Generate expt_rt.slx: IO324 force channels + host UDP link + FSM, for the Speedgoat.
%   The .slx is generated, not hand-edited: git tracks this script and the block .m files.
%   Re-run after changing any block .m file or P.ai_channels; other P changes only need a
%   rebuild (start_expt_rt.m does it when sources are newer than the build).
%   Calibration (expt_cal.m) is NOT built in: the CAL_* Constant blocks read tunable
%   Simulink.Parameters (expt_tunables.m) that start_expt_rt / apply_expt_cal set on the target.
%
%   The IO324 blocks and the config set (speedgoat.tlc, 1 ms fixed step) are copied from
%   simulink/ReadForcePlates.slx, the lab's working analog-input test, then widened to
%   P.ai_channels.
%
%   Diagram (all at P.dt = 1 ms):
%     UDP Receive (port net.cmd_port) --data,len--> host_rx --start, host_ok, TT, n...--> fsm_expt
%     IO324 Analog input (P.ai_channels) --volts--> cop_from_plates --cop_xy, fz--> fsm_expt
%     CAL_C1, CAL_C2, CAL_ORIGIN_MM, CAL_DZ_MM, CAL_TARE_SEQ --> cop_from_plates
%     CAL_MIN_FZ_N, CAL_NOISE_FLOOR_N --> fsm_expt
%     Digital Clock --t--> host_rx, fsm_expt, pack_state
%     fsm_expt + host_rx echo + zeroed volts --> pack_state --312 bytes--> UDP Send (net.host_ip:net.state_port)
%   Logged to the target's file log: raw and zeroed volts, CoP, Fz, setpoint, state, trial, events, start, host_ok.

here = fileparts(mfilename('fullpath'));
addpath(here);
mdl = 'expt_rt';
ref = 'ReadForcePlates';
[P, net] = expt_params();
assignin('base', 'P', P);
tunables = expt_tunables();   % CAL_* Simulink.Parameters (ExportedGlobal) in the base workspace
load_system(fullfile(here, '..', '..', 'simulink', [ref '.slx']));
if bdIsLoaded(mdl)
    close_system(mdl, 0);
end
new_system(mdl);
checks = {};   % what to verify by hand in the block dialogs

% Config: copy the reference model's (Speedgoat target), then make it run until stopped.
cs = attachConfigSetCopy(mdl, getActiveConfigSet(ref), true);
setActiveConfigSet(mdl, cs.Name);
set_param(mdl, 'SolverType', 'Fixed-step', 'Solver', 'FixedStepDiscrete', ...
    'FixedStep', num2str(P.dt), 'StopTime', 'Inf', 'SignalLogging', 'on');

% --- Force channels: the three IO324 blocks from ReadForcePlates, widened ---
add_block([ref '/Setup'], [mdl '/Setup'], 'Position', [40 20 180 80]);
add_block([ref '/IO324 Analog setup'], [mdl '/AnalogSetup'], 'Position', [220 20 400 80]);
for k = 1:32
    set_param([mdl '/AnalogSetup'], sprintf('parAdcChannel%d', k), onoff(ismember(k, P.ai_channels)));
end
add_block([ref '/IO324 Analog input'], [mdl '/AnalogIn'], 'Position', [40 380 200 520]);
set_param([mdl '/AnalogIn'], 'parAiChannels', mat2str(P.ai_channels), 'parSampleTime', num2str(P.dt));
checks{end + 1} = sprintf('AnalogIn / AnalogSetup: channels %s enabled, +-5.12 V, 1 ms', mat2str(P.ai_channels));

% --- Clock ---
add_block('simulink/Sources/Digital Clock', [mdl '/Clock'], 'SampleTime', num2str(P.dt), ...
    'Position', [40 150 90 180]);

% --- Host -> Speedgoat: UDP Receive ---
rx = [mdl '/UDP Rx'];
add_block(udp_block('UDP Receive'), rx, 'Position', [40 230 200 300]);
set_param(rx, 'useHostTargetConn', 'on');   % bind to the host-target link, not the block's 10.10.10.x default
checks{end + 1} = set_any(rx, {'localPort', 'ipPort', 'port'}, num2str(net.cmd_port));
checks{end + 1} = set_any(rx, {'rcvWidth', 'receiveWidth', 'width', 'dataWidth', 'outputWidth', 'maxLength', 'msgLength'}, '112');
checks{end + 1} = set_any(rx, {'sampleTime', 'ts'}, num2str(P.dt));

% --- MATLAB Function blocks (bodies pasted from the .m files) ---
fn_block(mdl, 'host_rx', here, [300 140 480 330]);
fn_block(mdl, 'cop_from_plates', here, [300 400 480 480]);
fn_block(mdl, 'fsm_expt', here, [600 120 800 500]);
fn_block(mdl, 'pack_state', here, [950 80 1130 640]);

% UDP Receive: data -> host_rx/2; length -> host_rx/3 if the block has a length port.
add_line(mdl, 'Clock/1', 'host_rx/1', 'autorouting', 'on');
add_line(mdl, 'UDP Rx/1', 'host_rx/2', 'autorouting', 'on');
ph = get_param(rx, 'PortHandles');
if numel(ph.Outport) >= 2
    add_line(mdl, 'UDP Rx/2', 'host_rx/3', 'autorouting', 'on');
else
    % host_rx is safe with a held last packet (seq unchanged = no heartbeat, rows idempotent).
    add_block('simulink/Sources/Constant', [mdl '/RxLen'], 'Value', '112', 'Position', [220 300 250 320]);
    add_line(mdl, 'RxLen/1', 'host_rx/3', 'autorouting', 'on');
    checks{end + 1} = 'UDP Rx has no length output: using a constant 112 (OK, see host_rx.m)';
end
% The IO324 block has one output port per channel: mux them into the volts vector.
ph = get_param([mdl '/AnalogIn'], 'PortHandles');
n_ai = numel(ph.Outport);
add_block('simulink/Signal Routing/Mux', [mdl '/AiMux'], 'Inputs', num2str(n_ai), ...
    'Position', [230 380 235 520]);
for k = 1:n_ai
    add_line(mdl, sprintf('AnalogIn/%d', k), sprintf('AiMux/%d', k), 'autorouting', 'on');
end
add_line(mdl, 'AiMux/1', 'cop_from_plates/1', 'autorouting', 'on');

% Tunable calibration: one Constant block per CAL_* parameter. Sample time P.dt (not inf) so a
% setparam on the target reaches the block outputs on the next step.
% cop_from_plates(volts, C1, C2, origin_mm, dz_mm, tare_seq, P); fsm_expt(..., min_fz, noise_floor, P)
dest = {'CAL_C1', 'cop_from_plates/2'; 'CAL_C2', 'cop_from_plates/3'; 'CAL_ORIGIN_MM', 'cop_from_plates/4'; ...
        'CAL_DZ_MM', 'cop_from_plates/5'; 'CAL_TARE_SEQ', 'cop_from_plates/6'; ...
        'CAL_MIN_FZ_N', 'fsm_expt/8'; 'CAL_NOISE_FLOOR_N', 'fsm_expt/9'};
assert(isempty(setxor(dest(:, 1), tunables(:, 1))), 'build_expt_rt: wire every CAL_* from expt_tunables');
for k = 1:size(dest, 1)
    y = 560 + 40 * k;
    add_block('simulink/Sources/Constant', [mdl '/' dest{k, 1}], 'Value', dest{k, 1}, ...
        'SampleTime', num2str(P.dt), 'Position', [380 y 520 y + 25]);
    add_line(mdl, [dest{k, 1} '/1'], dest{k, 2}, 'autorouting', 'on');
end

% fsm_expt(t, start, host_ok, cop_xy, fz_total, TT, n_trials, min_fz, noise_floor, P)
add_line(mdl, 'Clock/1', 'fsm_expt/1', 'autorouting', 'on');
add_line(mdl, 'host_rx/1', 'fsm_expt/2', 'autorouting', 'on');
add_line(mdl, 'host_rx/2', 'fsm_expt/3', 'autorouting', 'on');
add_line(mdl, 'cop_from_plates/1', 'fsm_expt/4', 'autorouting', 'on');
add_line(mdl, 'cop_from_plates/2', 'fsm_expt/5', 'autorouting', 'on');
add_line(mdl, 'host_rx/3', 'fsm_expt/6', 'autorouting', 'on');
add_line(mdl, 'host_rx/4', 'fsm_expt/7', 'autorouting', 'on');

% pack_state(t, state, trial, sp, cop_xy, cop_sd, stable_s, fz_total, events, t_state, center,
%            radius, sd_thr, stable_need, n_trials, n_loaded, table_sum, host_ok, cmd_seq,
%            n_rejected, volts, P)
src = {'Clock/1', 'fsm_expt/2', 'fsm_expt/3', 'fsm_expt/1', 'cop_from_plates/1', 'fsm_expt/6', ...
       'fsm_expt/5', 'cop_from_plates/2', 'fsm_expt/8', 'fsm_expt/4', 'fsm_expt/7', 'fsm_expt/9', ...
       'fsm_expt/10', 'fsm_expt/11', 'host_rx/4', 'host_rx/5', 'host_rx/6', 'host_rx/2', 'host_rx/7', ...
       'host_rx/8', 'cop_from_plates/3'};
for k = 1:numel(src)
    add_line(mdl, src{k}, sprintf('pack_state/%d', k), 'autorouting', 'on');
end

% --- Speedgoat -> host: UDP Send ---
tx = [mdl '/UDP Tx'];
add_block(udp_block('UDP Send'), tx, 'Position', [1250 330 1410 390]);
set_param(tx, 'useHostTargetConn', 'on');
checks{end + 1} = set_any(tx, {'toAddress', 'remoteAddress', 'remoteIpAddress', 'ipAddress'}, ['''' net.host_ip '''']);
checks{end + 1} = set_any(tx, {'toPort', 'remotePort', 'ipPort'}, num2str(net.state_port));
checks{end + 1} = set_any(tx, {'sampleTime', 'ts'}, num2str(P.dt));
add_line(mdl, 'pack_state/1', 'UDP Tx/1', 'autorouting', 'on');
ph = get_param(tx, 'PortHandles');
if numel(ph.Inport) > 1
    % R2025b UDP Send: input 2 is Length (bytes to send, double).
    add_block('simulink/Sources/Constant', [mdl '/TxLen'], 'Value', '312', 'SampleTime', num2str(P.dt), ...
        'Position', [1160 400 1200 420]);
    add_line(mdl, 'TxLen/1', 'UDP Tx/2', 'autorouting', 'on');
end

% --- File log: the authoritative record on the target ---
log_port('AiMux', 1, 'volts');
log_port('cop_from_plates', 1, 'cop_xy');
log_port('cop_from_plates', 2, 'fz_total');
log_port('cop_from_plates', 3, 'volts_zeroed');
names = {'sp', 'state', 'trial', 't_state', 'stable_s', 'cop_sd', 'center', 'events'};
for k = 1:numel(names)
    log_port('fsm_expt', k, names{k});
end
log_port('host_rx', 1, 'start');
log_port('host_rx', 2, 'host_ok');

save_system(mdl, fullfile(here, [mdl '.slx']));
fprintf('Built %s.\nCheck in the block dialogs:\n', fullfile(here, [mdl '.slx']));
fprintf('  - %s\n', checks{~cellfun(@isempty, checks)});
fprintf('Then: start_expt_rt (builds, loads and starts it on the Speedgoat).\n');

    function log_port(blk, port, name)
        h = get_param([mdl '/' blk], 'PortHandles');
        set_param(h.Outport(port), 'DataLogging', 'on', 'Name', name);
    end
end

function fn_block(mdl, name, here, pos)
% MATLAB Function block whose body is <name>.m; its P input becomes a block Parameter.
blk = [mdl '/' name];
add_block('simulink/User-Defined Functions/MATLAB Function', blk, 'Position', pos);
chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', blk);
chart.Script = fileread(fullfile(here, [name '.m']));
param = chart.find('-isa', 'Stateflow.Data', 'Name', 'P');
param.Scope = 'Parameter';
end

function lib_blk = udp_block(name)
% The Simulink Real-Time UDP blocks (R2020b+). Library names have moved between releases.
for lib = {'slrealtimeiplib', 'slrealtimeudp', 'slrealtimelib'}   % slrealtimeiplib: R2025b
    try
        load_system(lib{1});
        hit = find_system(lib{1}, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'Name', name);
        if ~isempty(hit)
            lib_blk = hit{1};
            return;
        end
    catch
    end
end
error(['Could not find the Simulink Real-Time "%s" block. In the Library Browser, find it under ' ...
       'Simulink Real-Time > UDP, right-click > Help to see its library path, and add that to udp_block() ' ...
       'in build_expt_rt.m.'], name);
end

function msg = set_any(blk, candidates, value)
% Set the first dialog parameter whose name matches one of the candidates (case-insensitive).
% Returns a line for the "check by hand" list: the name used, or the names available.
dp = fieldnames(get_param(blk, 'DialogParameters'));
for c = candidates
    hit = dp(strcmpi(dp, c{1}));
    if ~isempty(hit)
        set_param(blk, hit{1}, value);
        msg = sprintf('%s: %s = %s', get_param(blk, 'Name'), hit{1}, value);
        return;
    end
end
msg = sprintf('%s: SET BY HAND to %s (none of %s; dialog has: %s)', get_param(blk, 'Name'), value, ...
    strjoin(candidates, '/'), strjoin(dp', ', '));
end

function s = onoff(b)
if b, s = 'on'; else, s = 'off'; end
end
