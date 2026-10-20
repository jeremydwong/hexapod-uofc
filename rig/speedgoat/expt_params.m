function [P, net] = expt_params()
%EXPT_PARAMS Parameters for the expt_rt model. Edit here.
%   [P, net] = expt_params()
%   P goes to the MATLAB Function blocks (block Parameter, from the base workspace).
%   net holds addresses and ports for build_expt_rt.m (kept out of P: no strings in blocks).
%   The trial table is NOT here: the host sends it over UDP before each run (host_rx.m).

P.dt = 0.001;                    % model step (s): 1 kHz

% Moves
P.return_speed_mm_s = 100;       % peak speed of the return to home (mm/s)
P.min_move_s = 0.2;              % no move shorter than this, whatever the speed

% Trial rows from the host are rejected unless they pass these checks.
% Safe single-axis targets at home height: measured limits on the M10 imitator
% (surge -306 / +273, sway +/-266 mm) minus a 25 mm margin. Rows: surge, sway.
P.limits_mm = [-281 248; -241 241];
P.max_peak_speed_mm_s = 500;
P.host_timeout_s = 0.5;          % host_ok drops if the host heartbeat stalls this long

% CoP processing
P.cop_tau_s = 0.5;               % time constant of the running mean / SD (s)
P.min_fz_N = 200;                % CoP gates need at least this total vertical force (someone standing)
P.noise_floor_N = 50;            % below this: plates empty, CoP gates are overridden (PLACEHOLDER until calibrated)
P.tare_s = 2;                    % load cells zeroed over the first tare_s after app start (plates empty!)
P.cop_center_auto = true;        % true: centre = running mean CoP at the moment Start goes high
P.cop_center_mm = [0 0];         % used when cop_center_auto is false (plate frame, mm)

% Analog inputs on the IO324-200k (module 1). ReadForcePlates (Aug 31 autosave) reads AI 1-12 as two
% groups of 6; order within a group assumed Bertec Fx Fy Fz Mx My Mz. P.plate(k).channels index into THIS list
% (position in the block's output vector), not the module's channel numbers.
P.ai_channels = 1:12;            % IO324 channels to read, at most 12 are sent to the host

% Force plates: PLACEHOLDERS until the lab's plates and channel order are known.
% Each plate: 6 calibrated channels [Fx Fy Fz Mx My Mz] (N, N*m) = C * volts.
P.plate(1).C = eye(6);           % RIGHT plate (AI 1-6; Fy confirmed by a push, 2026-10-20): volts -> [Fx Fy Fz Mx My Mz]
P.plate(1).channels = 1:6;       % positions in the analog input vector, in that order
P.plate(1).origin_mm = [250 0];  % plate centre in the shared frame (x = sway/right, y = surge/front)
P.plate(1).dz_mm = 0;            % depth of the plate's measurement origin below its surface
P.plate(2).C = eye(6);           % LEFT plate (AI 7-12)
P.plate(2).channels = 7:12;
P.plate(2).origin_mm = [-250 0];
P.plate(2).dz_mm = 0;

% Packets (rig/uofc_hexa/expt/packet.py and command.py)
P.magic = 1212504129;            % 'HEXA' as a big-endian uint32: Speedgoat -> host state
P.version = 2;
P.cmd_magic = 1213157204;        % 'HOST': host -> Speedgoat command
P.cmd_version = 1;

% Network. 192.168.7.x is the default host-target link (LABLOG 2026-10-07).
net.host_ip = '192.168.7.2';     % where the state stream goes
net.state_port = 25000;          % host listens here
net.cmd_port = 25001;            % Speedgoat listens here for host commands
end
