function [start, host_ok, TT, n_trials, n_loaded, table_sum, cmd_seq, n_rejected] = host_rx(t, data, len, P)
%HOST_RX Decode host commands: heartbeat, Start, and the trial table (MATLAB Function block, 1 kHz).
%
% Inputs
%   t      experiment time (s)
%   data   uint8 bytes from the UDP Receive block (width >= 112)
%   len    bytes received this step (0 when nothing arrived)
%   P      expt_params struct (block Parameter)
%
% Command packet: 14 little-endian doubles (112 bytes), sent by the host at ~100 Hz.
% Layout, shared with rig/uofc_hexa/expt/command.py:
%   1 magic ('HOST')  2 version  3 seq (heartbeat)  4 start  5 n_trials  6 row (1-based, 0 = none)
%   7-14 that row: random_s axis distance_mm peak_speed_mm_s thresh_seconds_cop_stable
%                  cop_radius_mm cop_sd_mm max_wait_s
%
% The host cycles through the rows while start = 0; the table only changes while start
% is 0, so it is frozen for the whole run. Every row is checked against P.limits_mm and
% the speed limit; a bad row is not stored and counts in n_rejected. The host compares
% table_sum with its own copy before sending start = 1 (sum of TT(k,j) * (8k + j)).
%
% Outputs
%   start     1 only when the host says start, the table is complete and the host is alive
%   host_ok   1 while the heartbeat (seq) has changed within P.host_timeout_s
%   TT        N_MAX x 8 trial table, columns as above
%   n_trials, n_loaded, table_sum, cmd_seq, n_rejected   echoed to the host in the state packet

N_MAX = 500;    % fixed sizes for code generation
CMD_N = 14;

persistent tbl have bad n last_seq t_seen start_l
if isempty(tbl)
    tbl = zeros(N_MAX, 8); have = false(N_MAX, 1); bad = false(N_MAX, 1);
    n = 0; last_seq = -1; t_seen = -1e9; start_l = false;
end

if len == 8 * CMD_N && numel(data) >= 8 * CMD_N
    v = typecast(uint8(data(1:8 * CMD_N)), 'double');
    if v(1) == P.cmd_magic && v(2) == P.cmd_version
        if v(3) ~= last_seq
            last_seq = v(3);
            t_seen = t;
        end
        start_l = v(4) ~= 0;
        if ~start_l
            nn = round(v(5));
            if nn ~= n && nn >= 0 && nn <= N_MAX
                n = nn;
                tbl(:) = 0;
                have(:) = false;
                bad(:) = false;
            end
            r = round(v(6));
            if r >= 1 && r <= n
                row = reshape(v(7:14), 1, 8);
                if row_ok(row, P)
                    tbl(r, :) = row;
                    have(r) = true;
                    bad(r) = false;
                else
                    tbl(r, :) = 0;
                    have(r) = false;
                    bad(r) = true;
                end
            end
        end
    end
end

host_ok = double(t - t_seen < P.host_timeout_s);
n_loaded = 0; n_rejected = 0; table_sum = 0;
for k = 1:n
    n_loaded = n_loaded + double(have(k));
    n_rejected = n_rejected + double(bad(k));
    for j = 1:8
        table_sum = table_sum + tbl(k, j) * (8 * k + j);
    end
end
loaded = n >= 1 && n_loaded == n;
start = double(start_l && loaded && host_ok);
TT = tbl;
n_trials = n;
cmd_seq = last_seq;
end

function ok = row_ok(row, P)
% random_s axis distance_mm peak_speed_mm_s thresh_s cop_radius_mm cop_sd_mm max_wait_s
ok = all(isfinite(row)) && (row(2) == 1 || row(2) == 2);
if ok
    lim = P.limits_mm(row(2), :);
    ok = row(3) >= lim(1) && row(3) <= lim(2) ...
        && row(4) > 0 && row(4) <= P.max_peak_speed_mm_s ...
        && row(1) >= 0 && row(5) > 0 && row(6) > 0 && row(7) > 0 && row(8) >= 0;
end
end
