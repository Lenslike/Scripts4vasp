#!/usr/bin/env python3
"""
Interactive Phonopy + VASP workflow manager.
"""

from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import List, Sequence, Tuple

from datetime import datetime

# 生成带时间戳的日志文件名
LOG_PATH = Path(f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
CONFIG_STATE_PATH = Path("workflow_state.json")


def setup_logging() -> logging.Logger:
    """Configure logging to stdout and the workflow log file."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("phonopy_workflow")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("=== 工作流会话开始 ===")
    logger.info("工作目录: %s", Path.cwd())
    return logger


def prompt_user(question: str, default: str | None = None) -> str:
    """Prompt the user and log both the question and the response."""
    logger = logging.getLogger("phonopy_workflow")
    prompt_text = f"{question}"
    if default:
        prompt_text += f" [{default}]"
    logger.info("提示: %s", prompt_text)
    while True:
        response = input(f"{prompt_text}: ").strip()
        if not response and default is not None:
            response = default
        logger.info("用户输入: %s", response if response else "<空>")
        if response:
            return response
        print("输入不能为空，请重试。")


def prompt_choice(question: str, choices: dict[str, str], default: str) -> str:
    """Prompt for a choice among predefined options."""
    default = default.strip()
    options = "/".join(f"{key}:{value}" for key, value in choices.items())
    while True:
        answer = prompt_user(f"{question} ({options})", default=default)
        key = answer.strip()
        if key in choices:
            return key
        print(f"无效选项，请输入以下之一：{', '.join(choices)}。")


def choose_stage() -> str:
    """Prompt for workflow stage selection."""
    display_options = {"1": "预处理", "2": "后处理", "3": "完整流程"}
    selection = prompt_choice(
        "请选择要执行的阶段 (1=仅预处理, 2=仅后处理, 3=完整流程)",
        choices=display_options,
        default="3",
    )
    stage_map = {"1": "pre", "2": "post", "3": "full"}
    return stage_map[selection]


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for a yes/no response."""
    default_char = "y" if default else "n"
    while True:
        reply = prompt_user(f"{question} (y/n)", default=default_char).lower()
        if reply in {"y", "yes"}:
            return True
        if reply in {"n", "no"}:
            return False
        print("请输入 y 或 n。")


def prompt_int_list(question: str, count: int, default: Sequence[int]) -> Tuple[int, ...]:
    """Prompt for a list of integers."""
    default_str = " ".join(str(x) for x in default)
    while True:
        response = prompt_user(question, default=default_str)
        parts = response.split()
        if len(parts) != count:
            print(f"需要输入 {count} 个整数，请用空格分隔。")
            continue
        try:
            values = tuple(int(part) for part in parts)
            return values
        except ValueError:
            print("请输入整数。")


def prompt_positive_int(question: str, default: int) -> int:
    """Prompt for a positive integer."""
    while True:
        response = prompt_user(question, default=str(default))
        try:
            value = int(response)
        except ValueError:
            print("请输入整数。")
            continue
        if value <= 0:
            print("请输入正整数。")
            continue
        return value


def format_command(command: Sequence[str]) -> str:
    """Return a readable command string with shell-style quoting."""
    return " ".join(shlex.quote(str(arg)) for arg in command)


def run_command(
    command: Sequence[str], *, capture_output: bool = True, log_output: bool = True, **kwargs
) -> subprocess.CompletedProcess:
    """Run a shell command and abort on failure."""
    logger = logging.getLogger("phonopy_workflow")
    logger.info("执行命令: %s", format_command(command))
    result = subprocess.run(command, capture_output=capture_output, text=True, **kwargs)
    if capture_output:
        if result.stdout and log_output:
            logger.info(result.stdout.strip())
        if result.stderr:
            logger.info("标准错误: %s", result.stderr.strip())
    if result.returncode != 0:
        logger.error("命令执行失败，返回值 %s", result.returncode)
        raise RuntimeError(f"命令执行失败: {format_command(command)}")
    return result


def run_command_capture(command: Sequence[str]) -> str:
    """Run a command and return stdout."""
    result = run_command(command, capture_output=True)
    return result.stdout


def run_bandplot_to_file(output_path: Path) -> None:
    """Run phonopy-bandplot and redirect output to a file, with graceful failure handling."""
    logger = logging.getLogger("phonopy_workflow")
    command = ["phonopy-bandplot", "--gnuplot"]
    logger.info("尝试执行命令: %s > %s", format_command(command), output_path)

    try:
        with output_path.open("w", encoding="utf-8") as handle:
            proc = subprocess.run(
                command,
                stdout=handle,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,  # 添加超时限制
            )

        if proc.stderr:
            logger.warning("phonopy-bandplot 标准错误: %s", proc.stderr.strip())

        if proc.returncode != 0:
            logger.warning("phonopy-bandplot 执行失败（返回码 %d），可能是环境兼容性问题", proc.returncode)
            logger.info("[INFO] band.yaml 已生成。请在命令行手动运行 `phonopy-bandplot --gnuplot > phononband.out` 来获取绘图数据。")
            print("\n" + "=" * 60)
            print("[INFO] band.yaml 已生成。")
            print("phonopy-bandplot 命令执行失败，可能是环境兼容性问题。")
            print("请在命令行手动运行以下命令来获取绘图数据：")
            print("  phonopy-bandplot --gnuplot > phononband.out")
            print("=" * 60)
            # 不抛出异常，允许工作流继续
            return

        logger.info("phonopy-bandplot 输出已保存至 %s", output_path)

    except subprocess.TimeoutExpired:
        logger.warning("phonopy-bandplot 执行超时，跳过此步骤")
        logger.info("[INFO] band.yaml 已生成。请在命令行手动运行 `phonopy-bandplot --gnuplot > phononband.out` 来获取绘图数据。")
        print("\n" + "=" * 60)
        print("[INFO] band.yaml 已生成。")
        print("phonopy-bandplot 命令执行超时。")
        print("请在命令行手动运行以下命令来获取绘图数据：")
        print("  phonopy-bandplot --gnuplot > phononband.out")
        print("=" * 60)
    except Exception as exc:
        logger.warning("phonopy-bandplot 执行出错: %s", exc)
        logger.info("[INFO] band.yaml 已生成。请在命令行手动运行 `phonopy-bandplot --gnuplot > phononband.out` 来获取绘图数据。")
        print("\n" + "=" * 60)
        print("[INFO] band.yaml 已生成。")
        print(f"phonopy-bandplot 执行出错: {exc}")
        print("请在命令行手动运行以下命令来获取绘图数据：")
        print("  phonopy-bandplot --gnuplot > phononband.out")
        print("=" * 60)


@dataclass
class WorkflowConfig:
    stage: str
    dims: Tuple[int, int, int]
    prefix: str
    poscar_path: Path | None = None
    apply_symmetry: bool = True
    atom_name: str = "BO3"
    band_points: int = 51
    band_labels: str = "$\\Gamma$ M K $\\Gamma$"
    band_sequence: List[str] = field(default_factory=lambda: ["G", "M", "K", "G"])


def save_config_snapshot(config: WorkflowConfig) -> None:
    """Persist configuration needed for post-processing."""
    data = {
        "dims": list(config.dims),
        "prefix": config.prefix,
        "atom_name": config.atom_name,
        "band_points": config.band_points,
        "band_labels": config.band_labels,
        "band_sequence": config.band_sequence,
        "poscar_path": str(config.poscar_path) if config.poscar_path else None,
        "apply_symmetry": config.apply_symmetry,
    }
    CONFIG_STATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logging.getLogger("phonopy_workflow").info("预处理配置已记录到 %s", CONFIG_STATE_PATH.name)


def load_config_snapshot(stage: str) -> WorkflowConfig:
    """Load persisted configuration for post-processing."""
    logger = logging.getLogger("phonopy_workflow")
    if not CONFIG_STATE_PATH.exists():
        logger.error("=" * 60)
        logger.error("错误：未找到预处理配置文件")
        logger.error(f"配置文件路径: {CONFIG_STATE_PATH.absolute()}")
        logger.error("请先执行预处理阶段以生成必要的配置信息。")
        logger.error("=" * 60)
        print("\n" + "=" * 60)
        print("错误：未找到预处理配置文件")
        print(f"配置文件: {CONFIG_STATE_PATH.name}")
        print("请先执行预处理阶段以生成必要的配置信息。")
        print("=" * 60 + "\n")
        raise FileNotFoundError(
            "未找到预处理配置记录，请先执行预处理阶段以生成必要信息。"
        )
    try:
        data = json.loads(CONFIG_STATE_PATH.read_text(encoding="utf-8"))
        dims = tuple(int(value) for value in data["dims"])
        prefix = data["prefix"]
        atom_name = data.get("atom_name", "BO3")
        band_points = int(data.get("band_points", 51))
        band_labels = data.get("band_labels", r"$\Gamma$ M K $\Gamma$")
        band_sequence = list(data.get("band_sequence", ["G", "M", "K", "G"]))
        poscar_value = data.get("poscar_path")
        apply_symmetry = bool(data.get("apply_symmetry", True))
    except (KeyError, ValueError, TypeError) as exc:
        raise RuntimeError("已保存的预处理配置缺失或损坏，请重新执行预处理。") from exc

    poscar_path = Path(poscar_value).expanduser() if poscar_value else None
    logger.info("已加载预处理配置记录 (%s)。", CONFIG_STATE_PATH.name)
    logger.info("  - 扩胞倍数: %s", " ".join(str(d) for d in dims))
    logger.info("  - 文件夹前缀: %s", prefix)
    return WorkflowConfig(
        stage=stage,
        dims=dims,
        prefix=prefix,
        poscar_path=poscar_path,
        apply_symmetry=apply_symmetry,
        atom_name=atom_name,
        band_points=band_points,
        band_labels=band_labels,
        band_sequence=band_sequence,
    )


def collect_configuration(stage: str) -> WorkflowConfig:
    """Gather user configuration interactively or load existing state."""
    if stage == "post":
        return load_config_snapshot(stage)

    # 前处理阶段：收集用户输入
    # 1. 询问 POSCAR 文件名（假设在当前目录）
    poscar_path: Path | None = None
    while True:
        poscar_filename = prompt_user("请输入 POSCAR 文件名（当前目录下）", default="POSCAR")
        candidate = Path.cwd() / poscar_filename
        if candidate.exists():
            poscar_path = candidate.resolve()
            break
        print(f"未找到文件 {candidate}，请重试。")

    # 2. 询问是否执行对称性处理
    apply_symmetry = prompt_yes_no("是否执行 `phonopy --symmetry POSCAR`？", default=True)

    # 3. 询问扩胞倍数
    dims = prompt_int_list("请输入超胞倍数 (a b c)", count=3, default=(2, 2, 2))

    # 4. 询问文件夹前缀
    prefix = prompt_user("请输入声子任务文件夹前缀（例如 441Mono2bo3-disp）", default="441Mono2bo3-disp")

    # 5. ATOM_NAME 从 POSCAR 读取（在后处理时读取，这里设置占位）
    atom_name = "BO3"  # 默认值，后处理时会从 POSCAR-unitcell 读取

    # 6. 其他固定参数
    band_points = 51
    band_labels = r"$\Gamma$ M K $\Gamma$"
    band_sequence = ["G", "M", "K", "G"]

    config = WorkflowConfig(
        stage=stage,
        dims=dims,
        prefix=prefix,
        poscar_path=poscar_path,
        apply_symmetry=apply_symmetry,
        atom_name=atom_name,
        band_points=band_points,
        band_labels=band_labels,
        band_sequence=band_sequence,
    )
    save_config_snapshot(config)
    return config


def copy_poscar_to_workdir(source: Path, target: Path) -> None:
    """Copy the provided POSCAR file into the working directory."""
    logger = logging.getLogger("phonopy_workflow")
    logger.info("复制 POSCAR %s -> %s", source, target)
    try:
        if source.resolve() == target.resolve():
            logger.info("源 POSCAR 已位于当前目录，跳过复制。")
            return
    except OSError:
        pass
    shutil.copyfile(source, target)


def ensure_poscar_unitcell(apply_symmetry: bool) -> Path:
    """Prepare POSCAR-unitcell via phonopy symmetry or by renaming."""
    workdir = Path.cwd()
    poscar = workdir / "POSCAR"
    unitcell = workdir / "POSCAR-unitcell"
    if apply_symmetry:
        run_command(["phonopy", "--symmetry", "POSCAR"])
        generated = workdir / "PPOSCAR"
        if not generated.exists():
            raise FileNotFoundError("未找到 PPOSCAR，可能 `phonopy --symmetry` 执行失败。")
        logger = logging.getLogger("phonopy_workflow")
        if unitcell.exists():
            logger.info("检测到已存在 POSCAR-unitcell，删除后重新生成。")
            unitcell.unlink()
        generated.rename(unitcell)
    else:
        shutil.copyfile(poscar, unitcell)
    return unitcell


def run_displacements(config: WorkflowConfig, unitcell_path: Path) -> None:
    """Generate displaced structures with phonopy and reorganize them."""
    dim_args = [str(value) for value in config.dims]
    run_command(["phonopy", "-d", "--dim", *dim_args, "--pa", "auto", "-c", str(unitcell_path)])
    poscar_files = sorted(
        path for path in Path.cwd().glob("POSCAR-*") if path.is_file()
    )
    if not poscar_files:
        raise RuntimeError("未找到 phonopy 生成的 POSCAR-* 文件。")
    logger = logging.getLogger("phonopy_workflow")
    for src in poscar_files:
        name = src.name
        parts = name.split("-")
        if len(parts) != 2 or not parts[1].isdigit():
            logger.info("跳过无法识别的位移文件: %s", name)
            continue
        suffix = parts[1]
        dest_dir = Path(f"{config.prefix}-{suffix}")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_poscar = dest_dir / "POSCAR"
        if dest_poscar.exists():
            logger.info("覆盖已有文件: %s", dest_poscar)
            dest_poscar.unlink()
        logger.info("移动 %s -> %s", src, dest_poscar)
        shutil.move(str(src), dest_poscar)


def find_dispersion_folders(prefix: str) -> List[Path]:
    """Return sorted dispersion folders matching prefix-number pattern."""
    candidates = sorted(Path.cwd().glob(f"{prefix}-*"))
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    folders = [
        item
        for item in candidates
        if item.is_dir() and pattern.match(item.name)
    ]
    if not folders:
        raise RuntimeError(f"未找到以 {prefix} 为前缀的声子计算文件夹。")
    return folders


def check_convergence(folder: Path) -> None:
    """Replicate convergence detection logic for a single folder."""
    logger = logging.getLogger("phonopy_workflow")
    outcar = folder / "OUTCAR"
    if not outcar.exists():
        raise RuntimeError(f"{folder} 缺少 OUTCAR。")
    keyword_converged = "aborting loop because EDIFF is reached"
    keyword_finished = "Voluntary"
    converged = False
    finished = False
    with outcar.open("r", errors="ignore") as handle:
        for line in handle:
            if keyword_converged in line:
                converged = True
            if keyword_finished in line:
                finished = True
            if converged and finished:
                break
    if not (converged and finished):
        state = []
        if not converged:
            state.append("EDIFF 条件未满足")
        if not finished:
            state.append("计算未正常结束")
        reason = "/".join(state) if state else "原因未知"
        logger.error("收敛性检测失败: %s (%s)", folder, reason)
        raise RuntimeError(f"{folder} 未收敛: {reason}")
    logger.info("收敛性检测通过: %s", folder)


def clean_empty_files(folder: Path) -> None:
    """Remove zero-byte files inside the folder."""
    logger = logging.getLogger("phonopy_workflow")
    removed = 0
    for child in folder.iterdir():
        if child.is_file() and child.stat().st_size == 0:
            child.unlink()
            removed += 1
    if removed:
        logger.info("目录 %s: 删除 %d 个空文件", folder, removed)


def collect_vasprun_paths(folders: Sequence[Path]) -> List[Path]:
    """Ensure vasprun.xml exists in each folder."""
    paths: List[Path] = []
    for folder in folders:
        vasprun = folder / "vasprun.xml"
        if not vasprun.exists():
            raise RuntimeError(f"{folder} 缺少 vasprun.xml。")
        if vasprun.stat().st_size == 0:
            raise RuntimeError(f"{vasprun} 文件为空，请检查 VASP 计算是否完成。")
        paths.append(vasprun)
    return paths


def read_atom_name_from_poscar(poscar_path: Path) -> str:
    """Read element symbols from POSCAR file and concatenate them."""
    logger = logging.getLogger("phonopy_workflow")
    try:
        with poscar_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) < 6:
                raise ValueError("POSCAR 文件格式不完整")
            # VASP5 格式：第6行是元素符号
            element_line = lines[5].strip()
            elements = element_line.split()
            # 组合所有元素符号
            atom_name = "".join(elements)
            logger.info(f"从 POSCAR 读取到元素: {atom_name}")
            return atom_name
    except Exception as exc:
        logger.warning(f"无法从 POSCAR 读取元素信息: {exc}，使用默认值 BO3")
        return "BO3"


def determine_band_path(
    unitcell_path: Path
) -> Tuple[List[str], List[Tuple[float, float, float]], str]:
    """Determine band-path coordinates using ASE and allow user customization."""
    logger = logging.getLogger("phonopy_workflow")

    # 尝试使用 ASE 获取建议路径
    try:
        from ase.io import read

        atoms = read(str(unitcell_path))
        cell = atoms.cell

        # 获取晶格类型
        from ase.dft.kpoints import get_special_points
        special_points = get_special_points(cell)

        # 显示 ASE 建议的高对称点
        logger.info("=" * 60)
        logger.info("ASE 检测到的高对称点：")
        for symbol, coords in sorted(special_points.items()):
            logger.info(f"  {symbol}: ({coords[0]:.6f}, {coords[1]:.6f}, {coords[2]:.6f})")
        logger.info("=" * 60)

        print("\n检测到的高对称点：")
        for symbol, coords in sorted(special_points.items()):
            print(f"  {symbol}: ({coords[0]:.6f}, {coords[1]:.6f}, {coords[2]:.6f})")

        # 建议默认路径
        default_path = "G M K G"
        print(f"\n建议的默认路径: {default_path}")

        # 询问用户是否自定义
        path_input = prompt_user(
            "请输入高对称点路径（空格分隔，例如 G M K G）",
            default=default_path
        )
        band_sequence = [token.strip().upper() for token in path_input.split() if token.strip()]

        if len(band_sequence) < 2:
            raise ValueError("至少需要两个高对称点。")

        # 转换为坐标
        coordinates: List[Tuple[float, float, float]] = []
        for symbol in band_sequence:
            # Gamma 点的特殊处理
            search_symbol = symbol
            if symbol == "G":
                search_symbol = "Γ"
            elif symbol == "GAMMA":
                search_symbol = "Γ"

            if search_symbol in special_points:
                coord = special_points[search_symbol]
                coordinates.append((float(coord[0]), float(coord[1]), float(coord[2])))
            elif symbol in special_points:
                coord = special_points[symbol]
                coordinates.append((float(coord[0]), float(coord[1]), float(coord[2])))
            else:
                # 如果找不到，使用默认值
                logger.warning(f"未找到高对称点 {symbol}，使用默认坐标")
                fallback_points = {
                    "G": (0.0, 0.0, 0.0),
                    "M": (0.5, 0.0, 0.0),
                    "K": (1.0 / 3.0, -1.0 / 3.0, 0.0),
                }
                if symbol in fallback_points:
                    coordinates.append(fallback_points[symbol])
                else:
                    raise RuntimeError(f"未知高对称点 {symbol}")

        # 生成 BAND_LABELS
        band_labels_parts = []
        for symbol in band_sequence:
            if symbol == "G":
                band_labels_parts.append("$\\Gamma$")
            else:
                band_labels_parts.append(symbol)
        band_labels = " ".join(band_labels_parts)

        logger.info("使用 ASE 生成高对称路径: %s", " ".join(band_sequence))
        return band_sequence, coordinates, band_labels

    except ModuleNotFoundError:
        logger.warning("未检测到 ASE 模块，改用内置默认路径。")
    except Exception as exc:
        logger.warning("ASE 生成高对称路径失败 (%s)，改用内置默认值。", exc)

    # 如果 ASE 失败，使用默认值
    logger.info("使用内置默认高对称路径")
    default_sequence = ["G", "M", "K", "G"]
    fallback_points = {
        "G": (0.0, 0.0, 0.0),
        "M": (0.5, 0.0, 0.0),
        "K": (1.0 / 3.0, -1.0 / 3.0, 0.0),
    }
    coords: List[Tuple[float, float, float]] = [fallback_points[s] for s in default_sequence]
    band_labels = "$\\Gamma$ M K $\\Gamma$"

    return default_sequence, coords, band_labels


def write_band_conf(
    config: WorkflowConfig,
    unitcell_path: Path,
) -> None:
    """Create the band.conf file."""
    # 从 POSCAR-unitcell 读取元素名称
    atom_name = read_atom_name_from_poscar(unitcell_path)

    # 获取高对称点路径（包含用户交互）
    band_sequence, coordinates, band_labels = determine_band_path(unitcell_path)

    logger = logging.getLogger("phonopy_workflow")
    logger.info("=" * 60)
    logger.info("生成的高对称点路径信息：")
    for label, coord in zip(band_sequence, coordinates):
        logger.info("  %s -> (%.6f %.6f %.6f)", label, *coord)
    logger.info("=" * 60)

    # 构建 BAND 行
    band_values: List[str] = []
    for coord in coordinates:
        band_values.extend(f"{value:.6f}" for value in coord)
    band_line = " ".join(band_values)

    # 构建 DIM 行
    dim_values = " ".join(str(value) for value in config.dims)

    # 生成 band.conf 内容
    contents = [
        f"ATOM_NAME = {atom_name}",
        f"DIM = {dim_values}",
        f"BAND = {band_line}",
        f"BAND_POINTS = {config.band_points}",
        f"BAND_LABELS = {band_labels}",
        "BAND_CONNECTION = .TRUE.",
        "FORCE_CONSTANTS = WRITE",
        "FC_SYMMETRY = .TRUE.",
        "FC_FORMAT = HDF5",
    ]
    Path("band.conf").write_text("\n".join(contents) + "\n", encoding="utf-8")
    logger.info("band.conf 写入完成。")


def run_postprocessing(config: WorkflowConfig) -> None:
    """Execute convergence checks, force-set generation, and band calculations."""
    logger = logging.getLogger("phonopy_workflow")
    unitcell = Path("POSCAR-unitcell")
    if not unitcell.exists():
        raise FileNotFoundError("缺少 POSCAR-unitcell，无法执行后处理。")

    folders = find_dispersion_folders(config.prefix)
    logger.info(f"找到 {len(folders)} 个声子计算文件夹")

    # 收敛性检查
    unconverged_folders: List[Path] = []
    for folder in folders:
        try:
            check_convergence(folder)
        except RuntimeError as e:
            unconverged_folders.append(folder)
            logger.error(f"收敛性检查失败: {folder.name}")

    # 如果有未收敛的文件夹，记录并退出
    if unconverged_folders:
        logger.error("=" * 60)
        logger.error("发现未收敛的计算文件夹，后处理终止。")
        logger.error(f"未收敛文件夹数量: {len(unconverged_folders)}")
        logger.error("未收敛文件夹列表:")
        for folder in unconverged_folders:
            logger.error(f"  - {folder.name}")
        logger.error("=" * 60)

        print("\n" + "=" * 60)
        print("错误：发现未收敛的计算文件夹")
        print(f"未收敛文件夹数量: {len(unconverged_folders)}")
        print("详细信息已记录到日志文件")
        print("=" * 60)
        raise RuntimeError(f"发现 {len(unconverged_folders)} 个未收敛的文件夹，后处理终止。")

    logger.info("所有文件夹收敛性检查通过")

    # 清除空文件
    for folder in folders:
        clean_empty_files(folder)

    # 收集 vasprun.xml
    vasprun_paths = collect_vasprun_paths(folders)
    run_command(["phonopy", "-f", *[str(path) for path in vasprun_paths]])

    force_sets = Path("FORCE_SETS")
    if not force_sets.exists() or force_sets.stat().st_size == 0:
        raise RuntimeError(
            "phonopy -f 执行结束但未生成有效的 FORCE_SETS，请检查 vasprun.xml 和输出日志。"
        )
    logger.info(
        "FORCE_SETS 已成功生成 (大小 %.1f kB)", force_sets.stat().st_size / 1024
    )

    # 生成 band.conf 并计算声子谱
    write_band_conf(config, unitcell)
    run_command(["phonopy", "-c", str(unitcell), "band.conf", "-p", "-s"])
    run_bandplot_to_file(Path("phononband.out"))


def run_preprocessing(config: WorkflowConfig) -> None:
    """Execute pre-processing tasks."""
    if not config.poscar_path:
        raise RuntimeError("预处理阶段必须提供 POSCAR 文件。")
    work_poscar = Path("POSCAR")
    copy_poscar_to_workdir(config.poscar_path, work_poscar)
    unitcell = ensure_poscar_unitcell(config.apply_symmetry)
    run_displacements(config, unitcell)


def main() -> None:
    logger = setup_logging()
    try:
        stage = choose_stage()
        config = collect_configuration(stage)
        if config.stage in {"pre", "full"}:
            logger.info("开始执行预处理阶段")
            run_preprocessing(config)
        if config.stage in {"post", "full"}:
            logger.info("开始执行后处理阶段")
            run_postprocessing(config)
        logger.info("=== 工作流执行完成 ===")
    except Exception as exc:  # noqa: BLE001 - top-level error handler
        logger.exception("工作流执行失败: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
