function [sp, state, trial, t_state, stable_s, cop_sd, center, events, radius, sd_thr, stable_need] = ...
    fsm_expt(t, start, host_ok, cop_xy, fz_total, TT, n_trials, P)
%FSM_EXPT Trial state machine for the perturbation experiment (MATLAB Function block, 1 kHz).
%
% Inputs
%   t         experiment time (s), from a Digital Clock at P.dt
%   start     run flag from host_rx: 1 = run the trial list
%   host_ok   1 while the host heartbeat is alive (host_rx); 0 stops motion
%   cop_xy    [x y] combined CoP (mm), plate frame, from cop_from_plates
%   fz_total  total vertical force (N)
%   TT        trial table from host_rx, one row per trial, columns:
%             1 random_s  2 axis (1 surge, 2 sway)  3 distance_mm  4 peak_speed_mm_s
%             5 thresh_seconds_cop_stable  6 cop_radius_mm  7 cop_sd_mm  8 max_wait_s
%   n_trials  number of real rows in TT
%   P         expt_params struct (block Parameter)
%
% Outputs
%   sp        [sway surge heave] setpoint (mm) for the host to relay to the hexapod
%   state     0 IDLE, 1 HOMED, 2 MOVETGT, 3 WAIT_COP, 4 RETURN, 5 DONE, 9 FAULT
%   trial     current trial (1-based)
%   t_state   time in the current state (s)
%   stable_s  how long the CoP has been continuously stable (s), in WAIT_COP
%   cop_sd    running CoP standard deviation, sqrt(var_x + var_y) (mm)
%   center    CoP centre used for "near centre" (mm)
%   events    pulses, summed bits: 1 perturbation start, 2 arrived, 4 return start,
%             8 trial done, 16 fault
%   radius, sd_thr, stable_need   this trial's thresholds (for the host display)
%
% Sequence per trial: HOMED (wait random_s, then until the CoP is centred: within
% cop_radius_mm of the centre with running SD below cop_sd_mm) -> MOVETGT (open-loop smoothstep to
% distance_mm along the trial's axis at peak_speed_mm_s) -> WAIT_COP (until the CoP
% has stayed within cop_radius_mm of the centre with running SD below cop_sd_mm for
% thresh_seconds_cop_stable, or for max_wait_s if that is > 0) -> RETURN (smoothstep home at P.return_speed_mm_s) ->
% next trial, or DONE.
% Unloaded override: with fz_total below P.noise_floor_N (nobody on the plates) both CoP
% gates pass, so the protocol runs on an empty platform (start gate at once; return after
% thresh_seconds_cop_stable). Loads between the noise floor and P.min_fz_N wait.
% Start is ignored until t >= P.tare_s, while cop_from_plates zeroes the load cells.
% Stopping: start = 0 ends WAIT_COP early (returns home) and stops after the current
% trial; host_ok = 0 freezes the setpoint (FAULT) until the model is restarted.
% Heave is always 0: the host lifts the platform to home before Start and parks after.
%
% The Python mirror rig/uofc_hexa/expt/fsm.py implements the same logic; keep them in step.

S_IDLE = 0; S_HOMED = 1; S_MOVETGT = 2; S_WAIT_COP = 3; S_RETURN = 4; S_DONE = 5; S_FAULT = 9;

persistent st tr t_enter p0 p1 move_T stable m v ctr last_t sp_last
if isempty(st)
    st = S_IDLE; tr = 1; t_enter = t; p0 = zeros(1, 3); p1 = zeros(1, 3); move_T = 1;
    stable = 0; m = [0 0]; v = [0 0]; ctr = P.cop_center_mm; last_t = t; sp_last = zeros(1, 3);
end

dt = max(t - last_t, 0);
last_t = t;
events = 0;

% Running mean and variance of the CoP (exponentially weighted, time constant cop_tau_s).
valid = fz_total >= P.min_fz_N;
if valid
    a = min(dt / P.cop_tau_s, 1);
    d = cop_xy - m;
    m = m + a * d;
    v = (1 - a) * (v + a * d .^ 2);
end
cop_sd = sqrt(v(1) + v(2));
unloaded = fz_total < P.noise_floor_N;

n = max(n_trials, 1);
k = min(max(tr, 1), n);       % row of the current trial
% CoP "in the middle" for this trial, or nobody on the plates.
centred = unloaded || (valid && sqrt(sum((cop_xy - ctr) .^ 2)) < TT(k, 6) && cop_sd < TT(k, 7));
sp = sp_last;

% Host lost while the experiment is running: freeze where we are.
if ~host_ok && (st == S_HOMED || st == S_MOVETGT || st == S_WAIT_COP || st == S_RETURN)
    st = S_FAULT; t_enter = t; events = events + 16;
end

switch st
    case S_IDLE
        sp = zeros(1, 3);
        if start && host_ok && t >= P.tare_s
            if P.cop_center_auto
                ctr = m;
            else
                ctr = P.cop_center_mm;
            end
            tr = 1; k = 1;
            st = S_HOMED; t_enter = t;
        end

    case S_HOMED
        sp = zeros(1, 3);
        if ~start
            st = S_IDLE; t_enter = t;
        elseif t - t_enter >= TT(k, 1) && centred
            p0 = zeros(1, 3);
            p1 = zeros(1, 3);
            p1(axis_index(TT(k, 2))) = TT(k, 3);
            move_T = max(P.min_move_s, 1.875 * abs(TT(k, 3)) / TT(k, 4));
            st = S_MOVETGT; t_enter = t; events = events + 1;
        end

    case S_MOVETGT
        u = (t - t_enter) / move_T;
        sp = p0 + (p1 - p0) * smoothstep(u);
        if u >= 1
            sp = p1;
            stable = 0;
            st = S_WAIT_COP; t_enter = t; events = events + 2;
        end

    case S_WAIT_COP
        sp = p1;
        if centred
            stable = stable + dt;
        else
            stable = 0;
        end
        timed_out = TT(k, 8) > 0 && t - t_enter >= TT(k, 8);
        if stable >= TT(k, 5) || timed_out || ~start
            p0 = p1;
            p1 = zeros(1, 3);
            move_T = max(P.min_move_s, 1.875 * max(abs(p0)) / P.return_speed_mm_s);
            st = S_RETURN; t_enter = t; events = events + 4;
        end

    case S_RETURN
        u = (t - t_enter) / move_T;
        sp = p0 + (p1 - p0) * smoothstep(u);
        if u >= 1
            sp = zeros(1, 3);
            events = events + 8;
            tr = tr + 1;
            if ~start
                st = S_IDLE;
            elseif tr > n_trials
                st = S_DONE;
            else
                st = S_HOMED;
            end
            t_enter = t;
            k = min(tr, n);
        end

    case S_DONE
        sp = zeros(1, 3);
        if ~start
            st = S_IDLE; t_enter = t;
        end

    otherwise  % S_FAULT: hold the last setpoint
        sp = sp_last;
end

sp_last = sp;
state = st;
trial = min(tr, n);
t_state = t - t_enter;
stable_s = stable;
center = ctr;
radius = TT(k, 6);
sd_thr = TT(k, 7);
stable_need = TT(k, 5);
end

function s = smoothstep(u)
u = min(max(u, 0), 1);
s = u ^ 3 * (10 - 15 * u + 6 * u ^ 2);
end

function i = axis_index(ax)
% trial axis 1 = surge, 2 = sway -> index into [sway surge heave]
if ax == 1
    i = 2;
else
    i = 1;
end
end
