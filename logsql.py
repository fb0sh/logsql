#!/usr/bin/env python3
import sys
import os
import re
import shutil
import platform
import sqlite3
import pandas as pd
from tabulate import tabulate


def clear_screen():
    os.system("cls" if platform.system() == "Windows" else "clear")


def clean_string_column(col):
    return col.map(lambda x: x.strip() if isinstance(x, str) and x is not None else x)


def wrap_dataframe(df, max_width=None):
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


def read_log(file_path, has_header=True, sep=None, chunksize=None):
    if sep is None:
        sep = r"\s+" if not has_header else ","
    try:
        df_iter = pd.read_csv(
            file_path,
            sep=sep,
            engine="python",
            quotechar='"',
            on_bad_lines="skip",
            header=0 if has_header else None,
            chunksize=chunksize,
        )
        return df_iter, has_header
    except Exception:
        df_iter = pd.read_csv(
            file_path,
            sep=sep,
            engine="python",
            header=None,
            on_bad_lines="skip",
            chunksize=chunksize,
        )
        return df_iter, False


def load_dataframe_to_sqlite(conn, df_iter, table_name="current", is_header=True):
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {table_name}")
    for chunk in df_iter:
        # 无表头给列名
        if not is_header:
            chunk.columns = [f"_{i + 1}" for i in range(len(chunk.columns))]
        chunk.to_sql(table_name, conn, if_exists="append", index=False)


def execute_sql(conn, query):
    query = query.strip().rstrip(";")
    query = re.sub(r"\$(\d+)", r"_\1", query)
    try:
        df = pd.read_sql_query(query, conn)
        for col in df.select_dtypes(include="object"):
            df[col] = clean_string_column(df[col])
        return wrap_dataframe(df)
    except Exception as e:
        print(f"SQL 执行出错，请检查语法或列名: {e}")
        return None


def print_result(df, is_header=True):
    if df is None or df.empty:
        print("(0 rows)")
        return
    df_display = df.copy()
    if not is_header:
        df_display.columns = [
            f"${int(c[1:])}" if c.startswith("_") and c[1:].isdigit() else c
            for c in df_display.columns
        ]
    print(tabulate(df_display, headers="keys", tablefmt="grid", showindex=False))
    print(f"({len(df_display)} row{'s' if len(df_display) != 1 else ''})")


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
    print("  .sep <char>     Change separator")
    print("  .clear          Clear screen")
    print("  .help           Show help")
    print("  .q              Quit")


def handle_command(line, state):
    cmd = line[1:].strip()
    cmd_lower = cmd.lower()
    conn = state["conn"]
    if cmd_lower in ("q", "quit"):
        print("Exit.")
        sys.exit(0)
    elif cmd_lower == "help":
        print_help()
    elif cmd_lower.startswith("cols"):
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(current);")
        cols_info = cur.fetchall()
        cols = [row[1] for row in cols_info]
        cols_display = (
            cols if state["is_header"] else [f"${i + 1}" for i in range(len(cols))]
        )
        print("Columns:\n" + ", ".join(cols_display))
        if not state["df_empty"]:
            df = pd.read_sql_query("SELECT * FROM current LIMIT 1", conn)
            if not state["is_header"]:
                df.columns = cols_display
            print("\nFirst row preview:")
            print(tabulate(df, headers="keys", tablefmt="grid", showindex=False))
    elif cmd_lower.startswith("head"):
        n = 5
        parts = cmd.split()
        if len(parts) >= 2 and parts[1].isdigit():
            n = int(parts[1])
        df = pd.read_sql_query(f"SELECT * FROM current LIMIT {n}", conn)
        print_result(df, is_header=state["is_header"])
    elif cmd_lower.startswith("tail"):
        n = 5
        parts = cmd.split()
        if len(parts) >= 2 and parts[1].isdigit():
            n = int(parts[1])
        total = pd.read_sql_query("SELECT COUNT(*) AS c FROM current", conn)["c"][0]
        offset = max(total - n, 0)
        df = pd.read_sql_query(f"SELECT * FROM current LIMIT {n} OFFSET {offset}", conn)
        print_result(df, is_header=state["is_header"])
    elif cmd_lower.startswith("sep"):
        print(f"Current separator: {repr(state['sep'])}")
    elif cmd_lower == "clear":
        clear_screen()
    else:
        df = execute_sql(conn, line)
        print_result(df, is_header=state["is_header"])


def sql_cli(state):
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
            handle_command(line, state)
            continue
        buffer += (" " if buffer else "") + line
        if ";" in buffer:
            query = buffer
            buffer = ""
            df = execute_sql(state["conn"], query)
            print_result(df, is_header=state["is_header"])


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

    ext = os.path.splitext(file_path)[1].lower()
    force_no_header = ext != ".csv"

    chunksize = 100_000
    if force_no_header:
        df_iter, is_header = read_log(
            file_path, has_header=False, sep=sep if sep else r"\s+", chunksize=chunksize
        )
    else:
        df_iter, is_header = read_log(
            file_path, has_header=True, sep=sep, chunksize=chunksize
        )
        if not is_header:
            df_iter, is_header = read_log(
                file_path,
                has_header=False,
                sep=sep if sep else r"\s+",
                chunksize=chunksize,
            )

    conn = sqlite3.connect(":memory:")
    load_dataframe_to_sqlite(conn, df_iter, is_header=is_header)

    state = {"conn": conn, "is_header": is_header, "sep": sep, "df_empty": False}

    sql_cli(state)


if __name__ == "__main__":
    main()
