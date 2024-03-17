#!/bin/bash

# 统计当前目录下文件夹数目，记为n
n=$(ls -lR | grep "^d" | wc -l)

# 统计当前目录下各文件夹内OSZICAR含有特征词“1 F=”的数目，记为m
m=$(grep "1 F=" ./*/OSZICAR 2>/dev/null | wc -l)

# 判断条件n > m
if [[ $n -gt $m ]]; then
    echo "Feature Descriptor: The number of directories is greater than folders containing '1 F=' in OSZICAR files."
    # 打印不含有特征词“1 F=”的文件夹名称
    for dir in ./*; do
        if [[ -d "$dir" && ! -f "${dir}/OSZICAR" ]]; then
            echo "$dir"
        elif [[ -d "$dir" && -f "${dir}/OSZICAR" ]]; then
            if ! grep -q "1 F=" "${dir}/OSZICAR"; then
                echo "$dir"
            fi
        fi
    done
elif [[ $n -eq $m ]]; then
    echo "Feature Descriptor: The number of directories is equal to folders containing '1 F=' in OSZICAR files. Proceed to check 'DAV:  90'."
else
    echo "Feature Descriptor: Exiting because the condition 'n > m' is not met."
fi

# 无论之前的判断结果如何，现在统计包含"DAV:  90"特征词的OSZICAR文件数目，记为p
p=$(grep "DAV:  90" ./*/OSZICAR 2>/dev/null | wc -l)

# 如果包含"DAV:  90"特征词的文件数目p不为0，则输出包含该特征词的目录
if [[ $p -ne 0 ]]; then
    echo "Feature Descriptor: There are directories with 'DAV:  90' in OSZICAR files."
    grep "DAV:  90" ./*/OSZICAR -l | xargs -I '{}' dirname '{}'
elif [[ $p -eq 0 && $n -eq $m ]]; then
    echo "Feature Descriptor: None of the directories contain 'DAV:  90' in OSZICAR files. Exiting normally."
fi

# 脚本正常结束
exit 0
