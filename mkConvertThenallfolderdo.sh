#!/bin/bash

# 获取当前目录的绝对路径
current_dir=$(pwd)

# 先执行当前目录下的 movefile2folder.sh 脚本
if [ -e "$current_dir/movefile2folder.sh" ]; then
  # 如果文件存在且有执行权限
  if [ -x "$current_dir/movefile2folder.sh" ]; then
    bash "$current_dir/movefile2folder.sh"
  else
    echo "错误: 'movefile2folder.sh' 不可执行或不存在"
    exit 1
  fi
else
  echo "错误: 'movefile2folder.sh' 脚本不存在"
  exit 1
fi

# 然后执行当前目录下的 modiPOSCAR.sh 脚本
if [ -e "$current_dir/modiPOSCAR.sh" ]; then
  # 如果文件存在且有执行权限
  if [ -x "$current_dir/modiPOSCAR.sh" ]; then
    bash "$current_dir/modiPOSCAR.sh"
  else
    echo "错误: 'modiPOSCAR.sh' 不可执行或不存在"
    exit 1
  fi
else
  echo "错误: 'modiPOSCAR.sh' 脚本不存在"
  exit 1
fi

# 需要检查的文件
essential_files=("INCAR_scf" "POTCAR" "pbs.sh")

# 遍历当前目录下的所有子文件夹
for folder in "$current_dir"/*/; do
  if [ -d "$folder" ]; then
    # 检查所有必需的文件是否存在
    for file in "${essential_files[@]}"; do
      if [ ! -e "$current_dir/$file" ]; then
        echo "错误: 缺失必需的文件 '$current_dir/$file'"
        exit 1
      fi
    done

    # 检查qsub命令是否存在
    if ! command -v qsub &> /dev/null; then
      echo "错误: 'qsub' 命令未找到"
      exit 1
    fi

    cd "$folder"
    cp "$current_dir/INCAR_scf" ./INCAR
    cp "$current_dir/POTCAR" ./POTCAR
    cp "$current_dir/pbs.sh" ./
    # 提交作业
    if ! qsub pbs.sh; then
      echo "错误: 'qsub' 提交作业失败"
      # 返回初始目录以避免目录错乱
      cd "$current_dir"
      exit 1
    fi
    # 返回初始目录
    cd "$current_dir"
  fi
done
