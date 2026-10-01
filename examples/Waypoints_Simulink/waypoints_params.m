function P = waypoints_params()
%WAYPOINTS_PARAMS The sequence and safety limits for Waypoints_FSDI.slx. Edit here.
%   Axes and signs (code/ForceSeatDI_Structs.h): sway + right, surge + front,
%   heave + up, all mm from home (0,0,0). Rotations are always commanded zero.

% [sway surge heave] mm. Default: surge +30, surge -30, home, sway +30 (right),
% home, sway -30 (left), home. Same as test_from_park.py's default sequence.
P.W = [  0  30   0
         0 -30   0
         0   0   0
        30   0   0
         0   0   0
       -30   0   0
         0   0   0 ];
P.rest_s     = 3;     % s at each waypoint
P.rate       = 10;    % mm/s peak setpoint speed for waypoint moves
P.lift_rate  = 10;    % mm/s peak setpoint speed for lift from park and lowering back

% Safety
P.probe_s         = 0.5;     % s of read-only refresh before anything is sent
P.parked_below_mm = -100;    % refuse to start unless reported heave is below this (parked)
P.lowest_heave_mm = -165.0;  % parked pose is -165.65 mm, but FullMatch rejects it; -165.0 is
                             % accepted (measured on the M10, 2026-09-29)
P.track_tol_mm    = 20;      % stop sending if |reported - command| exceeds this on any axis
P.tilt_deg        = 0.5;     % stop sending if |roll|, |pitch| or |yaw| exceeds this
assert(all(abs(P.W(:)) < 50), 'Waypoints must stay within 50 mm of home');

% Run length: schedule from the nominal park pose, plus probe and margin.
S = [0 0 P.lowest_heave_mm];
t = 0;
done = false;
while ~done
    t = t + 0.05;
    [~, ~, done] = waypoint_schedule(t, S, P.W, P.rest_s, P.rate, P.lift_rate);
end
P.stop_time = P.probe_s + t + 3;
end
