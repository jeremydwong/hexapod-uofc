%TEST_FSM_EXPT Run fsm_expt.m in plain MATLAB (no Simulink, no Speedgoat) on synthetic CoP.
%   Same synthetic participant as the Python emulator (rig/uofc_hexa/expt/emulator.py):
%   quiet-stance sway plus a CoP shift against the platform move that recovers over 1.5 s.
%   Checks that every trial runs HOMED -> MOVETGT -> WAIT_COP -> RETURN and the list ends in DONE.

here = fileparts(mfilename('fullpath'));
addpath(here);
P = expt_params(fullfile(here, 'trials_example.csv'));
clear fsm_expt                       % reset its persistent state

dt = P.dt; t_end = 120;
n = round(t_end / dt);
rng(0);
stance = [0 20]; sway = [0 0]; settled = [0 0];
tau_sway = 0.8; sway_sd = 2; gain = 0.3; recover_s = 1.5;
sp = zeros(1, 3);
log = zeros(n, 9);   % t state trial sp_sway sp_surge cop_x cop_y cop_sd stable_s
for i = 1:n
    t = (i - 1) * dt;
    sway = sway - sway * dt / tau_sway + sway_sd * sqrt(2 * dt / tau_sway) * randn(1, 2);
    settled = settled + (sp(1:2) - settled) * dt / recover_s;
    cop = stance + sway - gain * (sp(1:2) - settled);
    [sp, state, trial, ~, stable_s, cop_sd] = fsm_expt(t, t >= 2, 1, cop, 700, P);
    log(i, :) = [t state trial sp(1) sp(2) cop cop_sd stable_s];
    if state == 5, log = log(1:i, :); break; end
end

states = log(:, 2);
fprintf('Finished at t = %.1f s in state %d (5 = DONE) after %d trials\n', log(end, 1), states(end), log(end, 3));
assert(states(end) == 5, 'trial list did not finish');
for k = 1:P.T.n   % each trial must visit MOVETGT, WAIT_COP and RETURN
    seen = unique(states(log(:, 3) == k));
    assert(all(ismember([2 3 4], seen)), 'trial %d skipped a state', k);
end
disp('All trials visited MOVETGT, WAIT_COP and RETURN.');

figure('Name', 'fsm_expt test');
subplot(3, 1, 1); stairs(log(:, 1), states); ylabel('state'); grid on;
yticks([0 1 2 3 4 5 9]); yticklabels({'IDLE', 'HOMED', 'MOVETGT', 'WAIT\_COP', 'RETURN', 'DONE', 'FAULT'});
subplot(3, 1, 2); plot(log(:, 1), log(:, 4:5)); ylabel('setpoint (mm)'); legend('sway', 'surge'); grid on;
subplot(3, 1, 3); plot(log(:, 1), log(:, 8), log(:, 1), log(:, 9)); ylabel('CoP SD (mm) / stable (s)');
legend('CoP SD', 'stable time'); xlabel('time (s)'); grid on;
