# Phonopy + VASP 声子计算工作流脚本使用说明

## 功能概述

本脚本实现了基于 Phonopy + VASP 的有限位移法声子计算的完整工作流，包括：

- **前处理**：准备位移结构文件，生成声子计算任务
- **后处理**：收敛性检查、力常数计算、声子谱生成

## 环境要求

### 必需软件
- Python 3.7+
- Phonopy（需要在环境变量中可用）
- VASP（用于实际计算，脚本不直接调用）

### 可选软件
- ASE (Atomic Simulation Environment) - 用于自动获取高对称点路径
  ```bash
  pip install ase
  ```

## 使用方法

### 基本运行

```bash
python workflow.py
```

脚本会交互式地询问您需要执行的阶段：
1. 仅预处理
2. 仅后处理
3. 完整流程

### 前处理流程

前处理阶段会执行以下步骤：

1. **输入 POSCAR 文件名**
   - 文件应位于当前工作目录
   - 示例：`POSCAR` 或 `POSCAR_initial`

2. **选择是否执行对称性处理**
   - 是：执行 `phonopy --symmetry POSCAR`，生成 PPOSCAR 并重命名为 POSCAR-unitcell
   - 否：直接将输入文件复制为 POSCAR-unitcell
   - 原始 POSCAR 文件会保留

3. **输入超胞倍数**
   - 格式：三个整数，用空格分隔
   - 示例：`2 2 2` 或 `4 4 1`
   - 这些数字表示在 a、b、c 方向上的扩胞倍数

4. **输入文件夹前缀**
   - 用于命名声子计算任务文件夹
   - 示例：`441Mono2bo3-disp`
   - 生成的文件夹格式：`{前缀}-001`, `{前缀}-002`, ...

#### 前处理输出

- `POSCAR-unitcell`：标准化的单胞结构
- `SPOSCAR`：超胞结构
- `phonopy_disp.yaml`：位移信息
- `{前缀}-001/`, `{前缀}-002/`, ...：包含 POSCAR 的任务文件夹
- `workflow_state.json`：保存的配置信息（供后处理使用）
- `workflow_YYYYMMDD_HHMMSS.log`：详细日志

### 后处理流程

后处理阶段会执行以下步骤：

1. **读取配置文件**
   - 自动加载前处理阶段保存的 `workflow_state.json`
   - 如果文件不存在，程序会提示并退出

2. **收敛性检查**
   - 检查所有声子计算文件夹中的 OUTCAR 文件
   - 验证是否满足 EDIFF 收敛条件
   - 如发现未收敛文件夹：
     - 打印警告信息
     - 将未收敛文件夹列表记录到日志
     - 退出后处理流程

3. **清除空文件**
   - 自动删除所有大小为 0 的文件
   - 不需要用户确认

4. **生成力常数**
   - 收集所有 `vasprun.xml` 文件
   - 执行 `phonopy -f ./*/vasprun.xml`
   - 生成 `FORCE_SETS` 文件

5. **生成 band.conf 配置**
   - 自动从 POSCAR-unitcell 读取元素信息设置 ATOM_NAME
   - 使用前处理阶段的扩胞倍数设置 DIM
   - 如果安装了 ASE：
     - 显示建议的高对称点
     - 允许用户自定义路径
   - 如果未安装 ASE：
     - 使用内置默认路径（Γ-M-K-Γ）

6. **计算声子谱**
   - 执行 `phonopy -c POSCAR-unitcell band.conf -p -s`
   - 生成 `band.yaml`、`FORCE_CONSTANTS` 等文件
   - 尝试导出文本格式声子谱数据到 `phononband.out`
   - 如果 `phonopy-bandplot` 命令执行失败（环境兼容性问题），会提示用户手动运行

#### 后处理输出

- `FORCE_SETS`：力常数数据
- `band.conf`：能带计算配置
- `band.yaml`：声子谱数据（主要输出文件）
- `FORCE_CONSTANTS` / `force_constants.hdf5`：力常数文件
- `phononband.out`：文本格式声子谱（如果自动生成成功）
- `workflow_YYYYMMDD_HHMMSS.log`：详细日志

**注意**：如果看到提示 "请在命令行手动运行 `phonopy-bandplot --gnuplot > phononband.out`"，说明自动导出步骤失败，您需要手动执行该命令来获取绘图数据。这不影响主要结果 `band.yaml` 的生成。

## 日志文件

- 日志文件名格式：`workflow_YYYYMMDD_HHMMSS.log`
- 每次运行创建带时间戳的新日志文件
- 以追加模式写入，记录详细的执行步骤和命令输出
- 日志内容包括：
  - 所有用户输入
  - 执行的命令及其输出
  - 高对称点坐标信息
  - 收敛性检查结果
  - 错误和警告信息

## 典型工作流程

### 场景 1：完整流程

```bash
# 1. 准备 POSCAR 文件在当前目录
# 2. 运行脚本
python workflow.py

# 3. 选择 "3" (完整流程)
# 4. 按提示输入参数
# 5. 前处理完成后，会自动继续后处理
```

### 场景 2：分步执行

```bash
# 第一步：仅执行前处理
python workflow.py
# 选择 "1" (仅预处理)
# 输入参数

# 第二步：完成 VASP 计算后，执行后处理
python workflow.py
# 选择 "2" (仅后处理)
# 脚本会自动读取前处理配置
```

## band.conf 参数说明

脚本生成的 band.conf 文件包含以下固定参数：

```
ATOM_NAME = [自动从POSCAR读取]
DIM = [前处理时输入的超胞倍数]
BAND = [根据高对称点生成]
BAND_POINTS = 51        # 固定值
BAND_LABELS = [根据路径生成]
BAND_CONNECTION = .TRUE.
FORCE_CONSTANTS = WRITE
FC_SYMMETRY = .TRUE.
FC_FORMAT = HDF5
```

## 错误处理

脚本遵循"遇错即停"原则：

- 任何关键步骤失败都会立即停止执行
- 打印错误信息到屏幕和日志
- 返回非零退出码

### 常见错误

1. **后处理时配置文件不存在**
   ```
   错误：未找到预处理配置文件
   解决：先执行预处理阶段
   ```

2. **收敛性检查失败**
   ```
   错误：发现未收敛的计算文件夹
   解决：检查日志中列出的文件夹，重新运行 VASP 计算
   ```

3. **POSCAR 文件不存在**
   ```
   未找到文件 XXX，请重试
   解决：确保文件在当前目录下
   ```

4. **phonopy-bandplot 执行失败**
   ```
   [INFO] band.yaml 已生成。
   phonopy-bandplot 命令执行失败，可能是环境兼容性问题。
   请在命令行手动运行以下命令来获取绘图数据：
     phonopy-bandplot --gnuplot > phononband.out
   ```
   这不是致命错误，主要的声子计算结果（band.yaml、FORCE_CONSTANTS 等）已经成功生成。只需要手动运行上述命令来获取绘图数据即可。

## 文件结构示例

```
工作目录/
├── POSCAR                        # 初始结构（用户提供）
├── POSCAR-unitcell               # 标准化单胞（脚本生成）
├── SPOSCAR                       # 超胞结构（脚本生成）
├── phonopy_disp.yaml             # 位移信息（脚本生成）
├── workflow_state.json           # 配置记录（脚本生成）
├── workflow_20260121_101134.log  # 日志文件（脚本生成）
├── 441Mono2bo3-disp-001/         # 声子计算文件夹
│   ├── POSCAR
│   ├── INCAR
│   ├── KPOINTS
│   ├── POTCAR
│   ├── OUTCAR                    # VASP 计算结果
│   └── vasprun.xml               # VASP 输出
├── 441Mono2bo3-disp-002/
│   └── ...
├── FORCE_SETS                    # 力常数（后处理生成）
├── band.conf                     # 能带配置（后处理生成）
├── band.yaml                     # 声子谱数据（后处理生成）
└── phononband.out                # 文本格式声子谱（后处理生成）
```

## 技术细节

### 收敛性检查逻辑

脚本检查每个计算文件夹的 OUTCAR 文件中是否包含：
- 关键词 1：`aborting loop because EDIFF is reached`（收敛）
- 关键词 2：`Voluntary`（正常结束）

只有同时满足这两个条件，才认为计算收敛。

### ATOM_NAME 读取

从 POSCAR 文件第 6 行读取元素符号（VASP5 格式），将所有元素连接成字符串。
例如：`B O` → `BO`

### 高对称点处理

- 优先使用 ASE 自动识别晶格类型并生成高对称点
- 用户输入 `G` 会自动映射到 Gamma 点（Γ）
- 如果 ASE 不可用，使用内置默认值（适用于六方晶格）

## 注意事项

1. **执行环境**
   - 确保 phonopy 命令在 PATH 中可用
   - 建议在 phonopy 虚拟环境中运行脚本

2. **VASP 计算**
   - 脚本不会自动提交 VASP 任务
   - 需要用户手动在每个 `{前缀}-XXX/` 文件夹中提交 VASP 计算
   - 后处理前确保所有计算已完成

3. **文件覆盖**
   - 脚本会覆盖已存在的同名文件（如 band.conf、FORCE_SETS）
   - 重要数据请提前备份

4. **配置文件**
   - `workflow_state.json` 对后处理至关重要
   - 不要手动修改或删除此文件
   - 如需重新执行前处理，可以删除此文件重新生成

## 参考

- Phonopy 文档：https://phonopy.github.io/phonopy/
- VASP 文档：https://www.vasp.at/
- ASE 文档：https://wiki.fysik.dtu.dk/ase/
