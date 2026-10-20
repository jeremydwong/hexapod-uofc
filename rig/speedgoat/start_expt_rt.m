function start_expt_rt(rebuild)
%START_EXPT_RT Build expt_rt if needed, then load and start it on the Speedgoat.
%   start_expt_rt          rebuilds only when a source is newer than expt_rt.mldatx
%   start_expt_rt(true)    always regenerates the model and rebuilds
%   From the host: uv run hexapod-expt-run --start-target   (runs this in matlab -batch)
%
%   The app then runs until stopped (StopTime Inf), idle until the host sends a trial
%   table and Start. Stop it with: tg = slrealtime; stop(tg)
%   To skip MATLAB on later sessions, make it boot with the target:
%   tg = slrealtime; setStartupApp(tg, 'expt_rt')

if nargin < 1, rebuild = false; end
here = fileparts(mfilename('fullpath'));
cd(here);
addpath(here);
mdl = 'expt_rt';
app = fullfile(here, [mdl '.mldatx']);

sources = [dir(fullfile(here, '*.m')); dir(fullfile(here, '..', '..', 'simulink', 'ReadForcePlates.slx'))];
sources = sources(~startsWith({sources.name}, 'test_'));
built = dir(app);
stale = isempty(built) || any([sources.datenum] > built.datenum);
if rebuild || stale
    build_expt_rt();
    [P, ~] = expt_params();
    assignin('base', 'P', P);
    slbuild(mdl);
end

tg = slrealtime;
connect(tg);
if isRunning(tg)
    fprintf('Stopping the running app first.\n');
    stop(tg);
end
load(tg, mdl);
start(tg);
fprintf('%s is running on %s. Now: uv run hexapod-expt-run\n', mdl, tg.TargetSettings.address);
end
