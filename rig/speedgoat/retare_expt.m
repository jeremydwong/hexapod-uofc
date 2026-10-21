function retare_expt()
%RETARE_EXPT Re-zero the load cells on the running app (plates EMPTY, Speedgoat idle).
%   cop_from_plates re-averages each channel over P.tare_s whenever CAL_TARE_SEQ changes;
%   Fz and CoP read zero meanwhile.

tg = slrealtime;
connect(tg);
seq = getparam(tg, '', 'CAL_TARE_SEQ');
setparam(tg, '', 'CAL_TARE_SEQ', seq + 1);
fprintf('Re-taring (keep the plates empty for 2 s)\n');
end
