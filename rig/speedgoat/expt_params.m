function P = expt_params(trials_csv)
%EXPT_PARAMS Parameters for the FSM_EXPT, COP and PACK blocks. Edit here.
%   P = expt_params('trials_example.csv')
%   The model reads P from the base workspace (tunable struct parameter).

if nargin < 1, trials_csv = fullfile(fileparts(mfilename('fullpath')), 'trials_example.csv'); end

P.dt = 0.001;                    % model step (s): 1 kHz
P.T = load_trials(trials_csv);   % trial table, padded to fixed size

% Moves
P.return_speed_mm_s = 100;       % peak speed of the return to home (mm/s)
P.min_move_s = 0.2;              % no move shorter than this, whatever the speed

% CoP processing
P.cop_tau_s = 0.5;               % time constant of the running mean / SD (s)
P.min_fz_N = 200;                % below this total vertical force: nobody on the plates
P.cop_center_auto = true;        % true: centre = running mean CoP at the moment Start goes high
P.cop_center_mm = [0 0];         % used when cop_center_auto is false (plate frame, mm)

% Force plates: PLACEHOLDERS until the lab's plates and channel order are known.
% Each plate: 6 calibrated channels [Fx Fy Fz Mx My Mz] (N, N*m) = C * volts.
P.plate(1).C = eye(6);           % left plate: volts -> [Fx Fy Fz Mx My Mz]
P.plate(1).channels = 1:6;       % which of the 12 analog inputs, in that order
P.plate(1).origin_mm = [-250 0]; % plate centre in the shared frame (x = sway/right, y = surge/front)
P.plate(1).dz_mm = 0;            % depth of the plate's measurement origin below its surface
P.plate(2).C = eye(6);           % right plate
P.plate(2).channels = 7:12;
P.plate(2).origin_mm = [250 0];
P.plate(2).dz_mm = 0;

% Packet
P.magic = 1212504129;            % 'HEXA' as a big-endian uint32, sent as a double
P.version = 1;
end
