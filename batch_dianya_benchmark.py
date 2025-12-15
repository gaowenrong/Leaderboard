#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import subprocess
import datetime

DEFAULT_DATASETS = [
    f"SPEECHIO_ASR_ZH{idx:05d}" for idx in range(23, 27)
]

# 如果命令行传入数据集列表，则用传入的；否则使用默认范围
DATASETS = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_DATASETS

MODEL_ID = "dianya_quality_api_zh"


def run_cmd(cmd, env=None):
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    return proc


def main():
    total_sets = len(DATASETS)
    leaderboard_root = os.path.abspath(os.path.dirname(__file__))

    # 日志文件：logs/batch_dianya_YYYYMMDD_HHMMSS.log
    logs_dir = os.path.join(leaderboard_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_dir, f"batch_dianya_{ts}.log")

    with open(log_path, "w", encoding="utf-8") as log_f:
        def log_line(msg="", end="\n", flush=True):
            sys.stdout.write(msg + end)
            if flush:
                sys.stdout.flush()
            log_f.write(msg + end)
            if flush:
                log_f.flush()

        def log_raw(s, flush=True):
            """直接写一段原始文本（带换行），用于子进程输出"""
            sys.stdout.write(s)
            if flush:
                sys.stdout.flush()
            log_f.write(s)
            if flush:
                log_f.flush()

        def log_status(status):
            """单行状态，终端用 \r 刷新，日志中按行追加"""
            sys.stdout.write("\r" + status)
            sys.stdout.flush()
            log_f.write(status + "\n")
            log_f.flush()

        log_line(f"日志文件: {log_path}")
        log_line(f"数据集列表: {', '.join(DATASETS)}")

        for idx, dataset in enumerate(DATASETS, start=1):
            header = f"===== 数据集 {idx}/{total_sets}: {dataset} ====="
            log_line("\n" + header)

            # 阶段：拉取
            stage = "拉取"
            log_line(f"[DATASET {idx}/{total_sets}] [阶段: {stage}] 正在拉取 {dataset} ...")
            pull_cmd = f"cd {leaderboard_root} && ops/pull -d {dataset}"
            pull_proc = run_cmd(pull_cmd)
            for line in pull_proc.stdout:
                log_raw(line)
            pull_proc.wait()
            if pull_proc.returncode != 0:
                log_line(f"拉取数据集 {dataset} 失败，退出。")
                sys.exit(pull_proc.returncode)

            # 阶段：测试
            stage = "测试"
            log_line(f"[DATASET {idx}/{total_sets}] [阶段: {stage}] 正在测试 {dataset} ...")
            env = os.environ.copy()
            env["NO_DOCKER_BUILD"] = "1"
            bench_cmd = f"cd {leaderboard_root} && ops/benchmark -m {MODEL_ID} -d {dataset}"
            bench_proc = run_cmd(bench_cmd, env=env)

            current_file = ""
            current_idx = 0
            total_files = 0

            for raw in bench_proc.stdout:
                line = raw.rstrip("\n")
                if line.startswith("[DY_PROGRESS]"):
                    try:
                        parts = line.split()
                        # [DY_PROGRESS] idx/total path
                        idx_part = parts[1]
                        current_file = parts[2] if len(parts) > 2 else ""
                        cur, tot = idx_part.split("/")
                        current_idx = int(cur)
                        total_files = int(tot)

                        frac_ds = f"{idx}/{total_sets}"
                        frac_file = f"{current_idx}/{total_files}" if total_files else "?/?"
                        perc_file = (current_idx / total_files * 100.0) if total_files else 0.0

                        status = (
                            f"[数据集 {frac_ds} {dataset}] "
                            f"[阶段: {stage}] "
                            f"[文件 {frac_file} ({perc_file:.2f}%)] "
                            f"[当前文件: {os.path.basename(current_file)}]"
                        )
                        log_status(status)
                    except Exception:
                        log_raw("\n" + line + "\n")
                else:
                    # 非进度行正常打印，避免覆盖最后一行
                    log_raw("\n" + line + "\n")

            bench_proc.wait()
            # 完成当前数据集，在最后刷新一行并换行
            if total_files:
                final_status = (
                    f"[数据集 {idx}/{total_sets} {dataset}] "
                    f"[阶段: {stage}] "
                    f"[文件 {current_idx}/{total_files} (100.00%)] "
                    f"[当前文件: {os.path.basename(current_file)}] 完成"
                )
                log_status(final_status)

            if bench_proc.returncode != 0:
                log_line(f"测试数据集 {dataset} 失败，退出。")
                sys.exit(bench_proc.returncode)

        log_line("\n所有数据集测试完成。")


if __name__ == "__main__":
    main()
