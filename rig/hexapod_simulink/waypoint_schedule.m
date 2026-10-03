function [xyz, seg, done] = waypoint_schedule(t, S, W, rest_s, rate, lift_rate)
%WAYPOINT_SCHEDULE Setpoint at time t for: S -> home, then each waypoint, then back to S.
%   t          seconds since the schedule started
%   S          1x3 start pose [sway surge heave] mm (the measured parked pose)
%   W          Nx3 waypoints [sway surge heave] mm, relative to home (0,0,0)
%   rest_s     seconds to rest at each waypoint
%   rate       mm/s peak setpoint speed for the waypoint moves
%   lift_rate  mm/s peak setpoint speed for the lift from S and the lowering back to S
%
%   Each move is a smoothstep (10u^3 - 15u^4 + 6u^5), whose peak speed is 1.875x
%   the mean, so its duration is 1.875 * distance / rate. Same profile as
%   rig/uofc_hexa/hexapod/test_from_park.py. Plain function, no state:
%   safe to call from a MATLAB Function block and from scripts.
%
%   seg: 0 = lift to home, k = waypoint k, N+1 = lower to S, N+2 = finished.

N = size(W, 1);
xyz = S;
seg = N + 2;
done = true;
t0 = 0;
prev = S;
for k = 0:N + 1
    if k == 0
        target = [0 0 0];
        r = lift_rate;
        hold_s = 2;
    elseif k <= N
        target = W(k, :);
        r = rate;
        hold_s = rest_s;
    else
        target = S;
        r = lift_rate;
        hold_s = 1;
    end
    T = max(1, 1.875 * max(abs(target - prev)) / r);
    if t < t0 + T + hold_s
        u = min(max((t - t0) / T, 0), 1);
        s = u^3 * (10 - 15*u + 6*u^2);
        xyz = prev + (target - prev) * s;
        seg = k;
        done = false;
        return;
    end
    t0 = t0 + T + hold_s;
    prev = target;
end
end
