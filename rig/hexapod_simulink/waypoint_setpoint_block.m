function [yaw, pitch, roll, heave, sway, surge, strategy, send_en, refresh_en, seg, fault] = ...
    waypoint_setpoint_block(t, act_sway, act_surge, act_heave, act_roll, act_pitch, act_yaw, P)
%WAYPOINT_SETPOINT_BLOCK Body of the "Setpoint" MATLAB Function block.
%   build_waypoints_model.m pastes this into the block; P is a block Parameter
%   (the struct from waypoints_params.m). Outputs 1-8 wire to the vendor
%   ForceSeatDI_PosPhy block (yaw, pitch, roll, heave, sway, surge, strategy,
%   enable); output 9 wires to ForceSeatDI_Refresh.
%
%   The vendor block sends maxSpeed = 65535 (no speed limit) and never pauses,
%   so this block is the only thing keeping motion slow and smooth:
%   1. For the first P.probe_s seconds it sends nothing and only refreshes, to
%      read the real pose.
%   2. It latches that pose as the start. It refuses to move (fault) unless the
%      platform is parked (heave below P.parked_below_mm). A pose of all zeros
%      also faults, since that is what the getters return before any data.
%   3. It follows waypoint_schedule from there.
%   4. If the reported pose ever strays more than P.track_tol_mm from the command,
%      or tilts beyond P.tilt_deg, it stops sending for good. The controller then
%      holds the last setpoint. Stop the simulation; the vendor terminate() parks.

persistent S latched faulted
if isempty(latched)
    S = [0 0 -165];
    latched = false;
    faulted = false;
end

yaw = 0; pitch = 0; roll = 0;          % always level
strategy = int32(1);                   % 1 = BestMatch, as in the vendor example
send_en = int32(0);
refresh_en = int32(1);                 % keep reading the pose, even after a fault
seg = -1;
fault = 0;
sway = act_sway; surge = act_surge; heave = act_heave;

act = [act_sway act_surge act_heave];
tilt = max(abs([act_roll act_pitch act_yaw])) * 180 / pi;

if t < P.probe_s
    return;                            % read only
end

if ~latched
    latched = true;
    S = [act_sway act_surge max(act_heave, P.lowest_heave_mm)];
    if all(act == 0) || act_heave > P.parked_below_mm || tilt > P.tilt_deg
        faulted = true;                % no data, not parked, or tilted: do not move
    end
end

[xyz, seg] = waypoint_schedule(t - P.probe_s, S, P.W, P.rest_s, P.rate, P.lift_rate);

if max(abs(act - xyz)) > P.track_tol_mm || tilt > P.tilt_deg
    faulted = true;
end

if faulted
    fault = 1;
    return;                            % send_en stays 0: controller holds the last setpoint
end

sway = xyz(1); surge = xyz(2); heave = xyz(3);
send_en = int32(1);
end
