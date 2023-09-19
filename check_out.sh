#!/usr/bin/env bash 
kwc='reached' # Key Word for Convergence
kwf='Voluntary' # Key word for job finish
soc=$(grep $kwc OUTCAR |tail -n 1 |awk '{print $1}')
sof=$(grep $kwf OUTCAR |tail -n 1 |awk '{print $1}')

if [ $soc=$kwc ]; then 
echo 'converged'
fi

if [ $sof=$kwf ]; then 
echo 'finished'
fi

if [ $soc=$kwc -a $sof=$kwf ]; then 
echo 'Perfect'
fi

