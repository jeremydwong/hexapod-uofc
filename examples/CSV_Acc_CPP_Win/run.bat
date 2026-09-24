rmdir /Q /S output 2> NUL
mkdir output

call CSV_Acc_CPP_Win motion/data.csv output/output_data.csv
