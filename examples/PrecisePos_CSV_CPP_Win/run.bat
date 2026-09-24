rmdir /Q /S output 2> NUL
mkdir output

call PrecisePos_CSV_CPP_Win motion/heave.csv output/out_heave.csv
call PrecisePos_CSV_CPP_Win motion/pitch.csv output/out_pitch.csv
call PrecisePos_CSV_CPP_Win motion/roll.csv output/out_roll.csv
call PrecisePos_CSV_CPP_Win motion/surge.csv output/out_surge.csv
call PrecisePos_CSV_CPP_Win motion/sway.csv output/out_sway.csv
call PrecisePos_CSV_CPP_Win motion/yaw.csv output/out_yaw.csv
