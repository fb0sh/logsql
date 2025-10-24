# logsql.py

一个 **SQLite3-like SQL CLI**，用于快速查询 CSV 或日志/文本文件。
支持标准 SQL（`SELECT ... FROM current WHERE ...`）和交互式 CLI，方便分析日志数据。

---

## 特性

* 支持 **CSV 文件** 和 **无表头文本日志**。
* 表名固定为 `current`。
* 支持标准 SQL 语句：

  * `SELECT ... FROM current WHERE ...`
  * `GROUP BY ...`, `ORDER BY ...`, `LIMIT ...`
* **显示行为**：

  * **CSV 文件**（有表头）：显示真实列名，如 `时间, 类型, 风险级别...`，查询时可使用列名。
  * **非 CSV 文件**（如 `.log`、`.txt`）：显示 `$1, $2, $3...`，内部列名 `_1, _2, _3...`，查询时可使用 `$N` 或 `_N`。
* 交互式 CLI：

  * `.cols` 显示列名
  * `.head [N]` 显示前 N 行（默认 5）
  * `.tail [N]` 显示后 N 行（默认 5）
  * `.sep <char>` 动态修改分隔符（如 `,`, `\t`, `\s+`）
  * `.clear` 清屏
  * `.help` 显示帮助
  * `.q` 退出
* 打印漂亮表格，长内容自动换行，去掉前后空白。

---

## 安装

1. 安装依赖：

```bash
pip install pandas tabulate pandasql
```

2. 下载 `logsql.py` 到本地。

---

## 使用

```bash
python logsql.py <file> [--sep ,|\t| ]
```

示例：

```bash
python logsql.py samples/waf_log.csv
python logsql.py samples/waf_log.log
```

---

## CSV 文件示例

文件：`waf_log.csv`

| 时间                  | 类型 | 风险级别 | 方法   | Host                                      | URL    | 客户端IP        | 错误码 | Referer | 动作 | WAF规则ID | WAF事件详情 |
| ------------------- | -- | ---- | ---- | ----------------------------------------- | ------ | ------------ | --- | ------- | -- | ------- | ------- |
| 2025-10-24 10:20:01 | 攻击 | 高    | POST | [www.example.com](http://www.example.com) | /login | 192.168.1.10 | 403 | -       | -  | -       | -       |
| 2025-10-24 10:22:15 | 扫描 | 中    | GET  | [www.example.com](http://www.example.com) | /admin | 192.168.1.11 | 200 | -       | -  | -       | -       |

启动 CLI：

```text
$ python logsql.py samples/waf_log.csv
SQLite3-like SQL CLI for table 'current'
Type SQL statements terminated with ';'
Built-in commands: .help, .cols, .head [N], .tail [N], .sep <char>, .clear, .q to quit
current> .cols
Columns:
时间, 类型, 风险级别, 方法, Host, URL, 客户端IP, 错误码, Referer, 动作, WAF规则ID, WAF事件详情

First row preview:
+---------------------+------+---------+------+----------------+--------+---------------+--------+---------+-----+-----------+-------------+
| 时间                | 类型 | 风险级别 | 方法 | Host           | URL    | 客户端IP       | 错误码 | Referer | 动作 | WAF规则ID | WAF事件详情 |
+=====================+======+=========+======+================+========+===============+========+=========+=====+===========+=============+
| 2025-10-24 10:20:01 | 攻击 | 高      | POST | www.example.com | /login | 192.168.1.10 | 403    | -       | -   | -         | -           |
+---------------------+------+---------+------+----------------+--------+---------------+--------+---------+-----+-----------+-------------+
```

查询示例：

```text
current> SELECT URL, Host, 风险级别 FROM current WHERE 风险级别='高';
+--------+----------------+---------+
| URL    | Host           | 风险级别 |
+========+================+=========+
| /login | www.example.com | 高      |
+--------+----------------+---------+
```

---

## 非 CSV 文件示例

文件：`waf_log.log`（无表头，空格/制表符分隔）：

```
2025-10-24 10:20:01 攻击 高 POST www.example.com /login 192.168.1.10 403
2025-10-24 10:22:15 扫描 中 GET www.example.com /admin 192.168.1.11 200
```

启动 CLI：

```text
$ python logsql.py samples/waf_log.log
SQLite3-like SQL CLI for table 'current'
Type SQL statements terminated with ';'
Built-in commands: .help, .cols, .head [N], .tail [N], .sep <char>, .clear, .q to quit
current> .cols
Columns:
$1, $2, $3, $4, $5, $6, $7, $8, $9

First row preview:
+----------------------+-------------------+------+-----+----------------+--------+----------------+-----+-----+
| $1                   | $2                | $3   | $4  | $5             | $6     | $7             | $8  | $9  |
+======================+===================+======+=====+================+========+================+=====+=====+
| 2025-10-24           | 10:20:01          | 攻击 | 高   | POST           | www.example.com | /login | 192.168.1.10 | 403 |
+----------------------+-------------------+------+-----+----------------+--------+----------------+-----+-----+
```

查询示例：

```text
current> SELECT $6, $7, $3 FROM current WHERE $3='攻击';
+----------------+--------+------+
| $6             | $7     | $3   |
+================+========+======+
| www.example.com | /login | 攻击 |
+----------------+--------+------+
```

---

## 小结

* **CSV 文件** → 用真实列名，方便阅读和 SQL 查询。
* **非 CSV 文件** → 用 `$1,$2,...` 列名显示，适合纯日志/无表头文本。
* CLI 支持 `.head`, `.tail`, `.cols`, `.sep` 等命令快速查看数据。
* 支持标准 SQL 查询，快速筛选和统计日志信息。

---
