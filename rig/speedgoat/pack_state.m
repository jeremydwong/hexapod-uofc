function pkt = pack_state(seq, t, state, trial, sp, cop_xy, cop_sd, stable_s, fz_total, events, ...
    t_state, center, radius, sd_thr, stable_need, P)
%PACK_STATE The 21-double state packet sent to the host every step (MATLAB Function block).
%   Feed pkt (21x1 double) to a Byte Packing block (all double, little-endian), then to
%   UDP Send (local IP: use host-target connection, or the dedicated real-time port;
%   remote: host IP, port 25000). Layout, shared with rig/uofc_hexa/expt/packet.py:
%     1 magic   2 version   3 seq   4 t (s)   5 state   6 trial
%     7-9  setpoint sway, surge, heave (mm)
%     10-11 CoP x, y (mm)   12 CoP SD (mm)   13 stable time (s)   14 Fz total (N)
%     15 events   16 time in state (s)   17-18 centre x, y (mm)
%     19 radius (mm)   20 SD threshold (mm)   21 stable time needed (s)
pkt = [P.magic; P.version; seq; t; state; trial; sp(:); cop_xy(:); cop_sd; stable_s; fz_total; ...
       events; t_state; center(:); radius; sd_thr; stable_need];
end
