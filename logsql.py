#!/usr/bin/env python3
"""
log_query_sql.py - 使用标准 SQL 查询日志
表名固定为 current
支持 CSV/无表头文本，中文列名
支持标准 SQL: select ... from current where ... group by ... order by ... limit ...
打印漂亮表格，长内容自动换行
"""

import sys
import os
import shutil
import pandas as pd
from tabulate import tabulate
from pandasql import sqldf

pysqldf = lambda q: sqldf(q, globals())


def read_log(file_path, has_header=True):
    if has_header:
        df = pd.read_csv(
            file_path, sep=",", engine="python", quotechar='"', on_bad_lines="skip"
        )
    else:
        df = pd.read_csv(file_path, sep=r"\s+", header=None, on_bad_lines="skip")
        df.columns = [f"${i + 1}" for i in range(len(df.columns))]
    return df


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


def execute_sql(df, query):
    """执行标准 SQL 查询，默认表名 current"""
    query = query.strip().rstrip(";")
    if "from" not in query.lower():
        query += " FROM current"

    try:
        globals()["current"] = df
        result = sqldf(query, globals())
        return wrap_dataframe(result)
    except Exception as e:
        print("SQL 执行出错，请检查语法或列名。")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python log_query_sql.py <csv_file> [SQL_query]")
        return

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return

    try:
        df = read_log(file_path, has_header=True)
    except:
        df = read_log(file_path, has_header=False)

    # 命令行提供 SQL 查询则执行一次
    if len(sys.argv) >= 3:
        sql_query = sys.argv[2]
        result = execute_sql(df, sql_query)
        print(tabulate(result, headers="keys", tablefmt="grid", showindex=False))
        return

    # 交互模式
    print("=== SQL 查询交互模式 ===")
    print("内建命令: cols (列名), head [N], help, q (退出)")
    while True:
        s = input("请输入 SQL 查询 (或输入 q 退出): ").strip()
        if s == "":
            continue
        if s.lower() == "q":
            print("退出程序。")
            break
        if s.lower() == "help":
            print(
                "示例: SELECT 时间, Host FROM current WHERE 风险级别='高' ORDER BY 时间 LIMIT 10;"
            )
            print("内建命令: cols (列名), head [N], help, q (退出)")
            continue
        if s.lower().startswith("cols"):
            print("列名:")
            for c in df.columns:
                print(" -", c)
            continue
        if s.lower().startswith("head"):
            parts = s.split()
            n = 5
            if len(parts) >= 2 and parts[1].isdigit():
                n = int(parts[1])
            print(
                tabulate(
                    wrap_dataframe(df.head(n)),
                    headers="keys",
                    tablefmt="grid",
                    showindex=False,
                )
            )
            continue
        # 否则当作 SQL 执行
        result = execute_sql(df, s)
        print(tabulate(result, headers="keys", tablefmt="grid", showindex=False))


if __name__ == "__main__":
    main()
