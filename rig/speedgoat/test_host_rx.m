function test_host_rx(cmd_file, state_file)
%TEST_HOST_RX Desktop test of host_rx -> cop_from_plates -> fsm_expt -> pack_state (no Simulink).
%   test_host_rx()                       builds its own command packets from trials_example.csv
%   test_host_rx(cmd_file, state_file)   replays command bytes (112 per packet, one packet per
%                                        10 ms, e.g. written by Python) and writes every state
%                                        packet's bytes to state_file, to check both byte layouts
%   Checks: rows load, a bad row is rejected, Start is gated on a complete table, every
%   trial runs, and the state packet is 312 bytes with the right magic.

here = fileparts(mfilename('fullpath'));
addpath(here);
P = expt_params();
clear host_rx fsm_expt                     % reset persistent state
dt = P.dt;

if nargin < 1
    [TT, n] = load_trials(fullfile(here, 'trials_example.csv'), P);
    cmds = make_commands(TT, n, P, 90);    % 90 s of commands, Start from 1 s
else
    fid = fopen(cmd_file, 'r'); raw = fread(fid, Inf, '*uint8'); fclose(fid);
    cmds = reshape(raw, 112, []);
    n = [];
end

% The first packet carries row 1 as sway 400 mm: it must be rejected, then replaced by
% the good row 1 on the next round.
if nargin < 1
    bad = typecast(cmds(:, 1), 'double');
    bad(8) = 2; bad(9) = 400;
    cmds(:, 1) = typecast(bad, 'uint8');
end

n_steps = size(cmds, 2) * 10;
out = zeros(312, n_steps, 'uint8');
log = zeros(n_steps, 6);                  % t state trial n_loaded n_rejected start
rejected_seen = false;
for i = 1:n_steps
    t = (i - 1) * dt;
    if mod(i - 1, 10) == 0
        data = cmds(:, (i - 1) / 10 + 1); len = 112;
    else
        data = zeros(112, 1, 'uint8'); len = 0;
    end
    [start, host_ok, TTt, n_trials, n_loaded, table_sum, cmd_seq, n_rejected] = host_rx(t, data, len, P);
    rejected_seen = rejected_seen || n_rejected > 0;
    volts = zeros(12, 1);
    cop_from_plates(volts, P);             % exercised, but unloaded plates give no CoP:
    cop_xy = [0 20]; fz = 700;             % use a synthetic, steady participant instead
    [sp, state, trial, t_state, stable_s, cop_sd, center, events, radius, sd_thr, stable_need] = ...
        fsm_expt(t, start, host_ok, cop_xy, fz, TTt, n_trials, P);
    out(:, i) = pack_state(t, state, trial, sp, cop_xy, cop_sd, stable_s, fz, events, t_state, center, ...
        radius, sd_thr, stable_need, n_trials, n_loaded, table_sum, host_ok, cmd_seq, n_rejected, volts, P);
    log(i, :) = [t state trial n_loaded n_rejected start];
end

v = typecast(out(:, end), 'double');
fprintf('Final: state %d, trial %d, table %d/%d, rejected %d, table_sum %.10g, host_ok %d\n', ...
    v(5), v(6), v(23), v(22), v(27), v(24), v(25));
assert(numel(v) == 39 && v(1) == P.magic && v(2) == P.version, 'bad state packet');
if nargin < 1
    assert(rejected_seen, 'the bad row was not rejected');
    assert(v(5) == 5, 'trial list did not finish (state %d)', v(5));
    for k = 1:n
        seen = unique(log(log(:, 3) == k, 2));
        assert(all(ismember([2 3 4], seen)), 'trial %d skipped a state', k);
    end
    disp('host_rx chain OK: bad row rejected, table loaded, all trials ran, packet layout OK.');
else
    fid = fopen(state_file, 'w'); fwrite(fid, out(:), 'uint8'); fclose(fid);
    fprintf('Wrote %d state packets to %s\n', n_steps, state_file);
end
end

function cmds = make_commands(TT, n, P, seconds)
% 100 Hz command packets: rows round robin until Start at 1 s, then Start = 1.
m = round(seconds * 100);
cmds = zeros(112, m, 'uint8');
for i = 1:m
    start = i > 100;
    r = mod(i - 1, n) + 1;
    row = TT(r, :);
    if start, r = 0; row = zeros(1, 8); end
    v = [P.cmd_magic; P.cmd_version; i; start; n; r; row(:)];
    cmds(:, i) = typecast(v, 'uint8');
end
end
