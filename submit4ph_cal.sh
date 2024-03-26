#!/usr/bin/env bash

# 获取当前脚本所在目录的绝对路径
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for((i=1; i<=60; i++)); do
    dir_name="disp-$(printf "%03d" $i)"
    mkdir -p "$dir_name"
    cp "POSCAR-$(printf "%03d" $i)" "$dir_name/POSCAR"
    cp "POTCAR" "$dir_name"
    cp "INCAR" "$dir_name"
    cp "KPOINTS" "$dir_name"
    cp "runvasp.sh" "$dir_name"
    (cd "$dir_name" && sbatch "runvasp.sh")
done
