function bytes = pack_state(t, state, trial, sp, cop_xy, cop_sd, stable_s, fz_total, events, ...
    t_state, center, radius, sd_thr, stable_need, n_trials, n_loaded, table_sum, host_ok, cmd_seq, ...
    n_rejected, volts, P)
%PACK_STATE The 39-double state packet sent to the host every step (MATLAB Function block).
%   bytes (312x1 uint8) goes straight to UDP Send (host IP, port 25000). Little-endian
%   doubles; layout shared with rig/uofc_hexa/expt/packet.py:
%     1 magic   2 version   3 seq (model step count)   4 t (s)   5 state   6 trial
%     7-9  setpoint sway, surge, heave (mm)
%     10-11 CoP x, y (mm)   12 CoP SD (mm)   13 stable time (s)   14 Fz total (N)
%     15 events   16 time in state (s)   17-18 centre x, y (mm)
%     19 radius (mm)   20 SD threshold (mm)   21 stable time needed (s)
%     22 n_trials   23 n_loaded   24 table_sum   25 host_ok   26 last host seq   27 n_rejected
%     28-39 analog inputs 1-12 (V), zero-padded
v12 = zeros(12, 1);
m = min(numel(volts), 12);
v12(1:m) = volts(1:m);
pkt = [P.magic; P.version; round(t / P.dt); t; state; trial; sp(:); cop_xy(:); cop_sd; stable_s; ...
       fz_total; events; t_state; center(:); radius; sd_thr; stable_need; ...
       n_trials; n_loaded; table_sum; host_ok; cmd_seq; n_rejected; v12];
bytes = typecast(pkt, 'uint8');
end
