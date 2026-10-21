function test_host_rx(cmd_file, state_file)
%TEST_HOST_RX Desktop test of host_rx -> cop_from_plates -> fsm_expt -> pack_state (no Simulink).
%   test_host_rx()                       builds its own command packets from trials_example.csv
%   test_host_rx(cmd_file, state_file)   replays command bytes (112 per packet, one packet per
%                                        10 ms, e.g. written by Python) and writes every state
%                                        packet's bytes to state_file, to check both byte layouts
%   Checks: rows load, a bad row is rejected, Start is gated on a complete table, every
%   trial runs, the state packet is 312 bytes with the right magic, and cop_from_plates
%   tares, re-tares on a CAL_TARE_SEQ change and puts a one-plate load at that plate's centre.

here = fileparts(mfilename('fullpath'));
addpath(here);
P = expt_params();
cal = expt_cal();
check_cop(cal, P);
clear host_rx fsm_expt cop_from_plates     % reset persistent state
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
    cop_from_plates(volts, cal.C1, cal.C2, cal.origin_mm, cal.dz_mm, 0, P);   % unloaded: no CoP,
    cop_xy = [0 20]; fz = 700;             % use a synthetic, steady participant instead
    [sp, state, trial, t_state, stable_s, cop_sd, center, events, radius, sd_thr, stable_need] = ...
        fsm_expt(t, start, host_ok, cop_xy, fz, TTt, n_trials, cal.min_fz_N, cal.noise_floor_N, P);
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

function check_cop(cal, P)
% Tare over P.tare_s, a pure Fz on each plate lands on its centre, a tare_seq change re-zeroes.
clear cop_from_plates
cop = @(v, seq) cop_from_plates(v, cal.C1, cal.C2, cal.origin_mm, cal.dz_mm, seq, P);
n_tare = round(P.tare_s / P.dt);
offset = 0.01 * (1:12)';
for i = 1:n_tare
    cop(offset, 0);
end
[~, fz, vz] = cop(offset, 0);
assert(fz == 0 && max(abs(vz)) < 1e-12, 'tare did not zero the inputs');
for k = 1:2
    v = offset;
    v(P.plate_channels(k, 3)) = v(P.plate_channels(k, 3)) + 1;   % +1 V on plate k's Fz only
    [xy, fz] = cop(v, 0);
    assert(abs(fz - cal.C1(3, 3) * (k == 1) - cal.C2(3, 3) * (k == 2)) < 1e-9, 'plate %d Fz scale', k);
    assert(max(abs(xy - cal.origin_mm(k, :))) < 1e-9, 'plate %d CoP %s not at its centre', k, mat2str(xy));
end
shifted = offset + 0.5;                    % new empty-plate offsets, then re-tare
for i = 1:n_tare
    [~, fz] = cop(shifted, 1);
    assert(fz == 0, 'outputs must read zero while re-taring');
end
[~, fz, vz] = cop(shifted, 1);
assert(fz == 0 && max(abs(vz)) < 1e-12, 're-tare did not zero the new offsets');
clear cop_from_plates
fprintf('cop_from_plates OK: tare, per-plate Fz %g/%g N per V at centres %s mm, re-tare.\n', ...
    cal.C1(3, 3), cal.C2(3, 3), mat2str(cal.origin_mm));
end
