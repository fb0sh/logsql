#!/usr/bin/env python3
"""
SQLite3-like SQL CLI for CSV/text logs
- 支持 CSV/无表头文本
- 表名固定为 current
- 支持标准 SQL: select ... from current where ... group by ... order by ... limit ...
- 有表头 CSV → 显示真实列名
- 无表头文本 → 显示 $1, $2 …，内部仍用 _N 列名
- 可通过 --sep 或 .sep 动态设置分隔符（例如 ',', '\t', ' '）
- 打印漂亮表格，长内容自动换行，去除前后空白
- 交互式 CLI 类似 SQLite3/MySQL

Behavior change: Files whose extension is NOT ".csv" are treated as no-header by default.
"""

import sys, os, re, shutil, platform
import pandas as pd
from tabulate import tabulate
from pandasql import sqldf

# ------------------------ 工具函数 ------------------------


def clear_screen():
    os.system("cls" if platform.system() == "Windows" else "clear")


def clean_string_column(col):
    return col.map(lambda x: x.strip() if isinstance(x, str) and x is not None else x)


def wrap_dataframe(df, max_width=None):
    """自动换行 DataFrame 内容"""
    if max_width is None:
        max_width = shutil.get_terminal_size((80, 20)).columns - 5
    df_wrapped = df.copy()
    for col in df.columns:
        df_wrapped[col] = (
            df_wrapped[col]
            .astype(str)
            .apply(
                lambda x: "\n".join(
                    [x[i : i + max_width] for i in range(0, len(x), max_width)]
                )
            )
        )
    return df_wrapped


def read_log(file_path, has_header=True, sep=None):
    """读取 CSV 或无表头文本"""
    if sep is None:
        sep = r"\s+" if not has_header else ","
    try:
        if has_header:
            df = pd.read_csv(
                file_path, sep=sep, engine="python", quotechar='"', on_bad_lines="skip"
            )
            # 如果 pandas 识别到自动生成列名，视为无表头
            if df.columns.str.contains("Unnamed").any():
                raise ValueError("No header detected")
            is_header = True
        else:
            df = pd.read_csv(file_path, sep=sep, header=None, on_bad_lines="skip")
            df.columns = [f"_{i + 1}" for i in range(len(df.columns))]
            is_header = False
    except Exception:
        # 任何读取异常都退到无表头解析
        df = pd.read_csv(file_path, sep=sep, header=None, on_bad_lines="skip")
        df.columns = [f"_{i + 1}" for i in range(len(df.columns))]
        is_header = False
    df = df.apply(lambda col: clean_string_column(col) if col.dtype == object else col)
    return df, is_header


def execute_sql(df, query):
    """执行 SQL 查询"""
    query = query.strip().rstrip(";")
    # 兼容 $1, $2 写法 → 内部 _N
    query = re.sub(r"\$(\d+)", r"_\1", query)

    try:
        globals()["current"] = df
        result = sqldf(query, globals())
        result = result.apply(
            lambda col: clean_string_column(col) if col.dtype == object else col
        )
        return wrap_dataframe(result)
    except Exception as e:
        print(f"SQL 执行出错，请检查语法或列名: {e}")
        return None


def print_result(df, is_header=True):
    if df is None or df.empty:
        print("(0 rows)")
        return
    df_display = df.copy()
    # 无表头时显示 $N
    if not is_header:
        df_display.columns = [
            f"${int(c[1:])}" if c.startswith("_") and c[1:].isdigit() else c
            for c in df_display.columns
        ]
    print(tabulate(df_display, headers="keys", tablefmt="grid", showindex=False))
    print(f"({len(df_display)} row{'s' if len(df_display) != 1 else ''})")


# ------------------------ CLI ------------------------


def print_help():
    print("Examples:")
    print("  SELECT * FROM current LIMIT 10;")
    print("  SELECT URL, Host FROM current WHERE 风险级别='高';")
    print(
        "  SELECT $1, $2 FROM current WHERE $3='something'; -- for files without header"
    )
    print("Built-in commands:")
    print("  .cols           Show columns")
    print("  .head [N]       Show first N rows")
    print("  .tail [N]       Show last N rows")
    print("  .sep <char>     Change separator (e.g. .sep ,  or  .sep \\t or .sep \\s+)")
    print("  .clear          Clear screen")
    print("  .help           Show this help message")
    print("  .q              Quit")


def handle_command(line, df, state):
    cmd = line[1:].strip()
    cmd_lower = cmd.lower()
    if cmd_lower in ("q", "quit"):
        print("Exit.")
        sys.exit(0)
    elif cmd_lower == "help":
        print_help()
    elif cmd_lower.startswith("cols"):
        if state["is_header"]:
            cols_display = df.columns.tolist()
        else:
            cols_display = [f"${int(c[1:])}" for c in df.columns]
        print("Columns:")
        print(", ".join(cols_display))
        if not df.empty:
            first_row = df.head(1).copy()
            if not state["is_header"]:
                first_row.columns = cols_display
            print("\nFirst row preview:")
            print(tabulate(first_row, headers="keys", tablefmt="grid", showindex=False))
    elif cmd_lower.startswith("head"):
        parts = cmd.split()
        n = 5
        if len(parts) >= 2 and parts[1].isdigit():
            n = int(parts[1])
        print_result(df.head(n), is_header=state["is_header"])
    elif cmd_lower.startswith("tail"):
        parts = cmd.split()
        n = 5
        if len(parts) >= 2 and parts[1].isdigit():
            n = int(parts[1])
        print_result(df.tail(n), is_header=state["is_header"])
    elif cmd_lower.startswith("sep"):
        parts = cmd.split(maxsplit=1)
        if len(parts) == 2:
            sep = parts[1].encode("utf-8").decode("unicode_escape")
            state["sep"] = sep
            print(f"Separator changed to: {repr(sep)}")
            df_new, is_header = read_log(
                state["file"], has_header=state["is_header"], sep=sep
            )
            state["df"] = df_new
            state["is_header"] = is_header
        else:
            print(f"Current separator: {repr(state['sep'])}")
    elif cmd_lower == "clear":
        clear_screen()
    else:
        print(f"Unknown command: {line}")


def sql_cli(df, file_path, sep, is_header):
    state = {"df": df, "file": file_path, "sep": sep, "is_header": is_header}
    print("SQLite3-like SQL CLI for table 'current'")
    print("Type SQL statements terminated with ';'")
    print(
        "Built-in commands: .help, .cols, .head [N], .tail [N], .sep <char>, .clear, .q to quit"
    )
    buffer = ""
    while True:
        prompt = "current> " if not buffer else "   ...> "
        try:
            line = input(prompt)
        except EOFError:
            print("\nExit.")
            break
        if not line.strip():
            continue
        if line.startswith("."):
            handle_command(line, state["df"], state)
            continue
        buffer += (" " if buffer else "") + line
        if ";" in buffer:
            query = buffer
            buffer = ""
            result = execute_sql(state["df"], query)
            print_result(result, is_header=state["is_header"])


# ------------------------ 主程序 ------------------------


def main():
    if len(sys.argv) < 2:
        print("Usage: python logsql.py <file> [--sep ,|\\t| ]")
        return
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"File doesn't exist: {file_path}")
        return

    sep = None
    if "--sep" in sys.argv:
        idx = sys.argv.index("--sep")
        if idx + 1 < len(sys.argv):
            sep = sys.argv[idx + 1].encode("utf-8").decode("unicode_escape")

    # If file extension is not .csv -> force no-header mode (treat as log)
    ext = os.path.splitext(file_path)[1].lower()
    force_no_header = ext != ".csv"

    if force_no_header:
        # default sep for no-header files is whitespace
        df, is_header = read_log(
            file_path, has_header=False, sep=sep if sep else r"\s+"
        )
    else:
        # CSV path: try reading as CSV with header, fallback to no-header if needed
        df, is_header = read_log(file_path, has_header=True, sep=sep)
        if not is_header:
            df, is_header = read_log(
                file_path, has_header=False, sep=sep if sep else r"\s+"
            )

    sql_cli(
        df, file_path, sep if sep else (r"\s+" if force_no_header else ","), is_header
    )


if __name__ == "__main__":
    main()
