# 青岚监测分区交接

青岚区环境监测中心在白班收齐正式盘点和具名质控差额，挑选本班交接的版本及证据。夜班在不连接来源库的工作站用固定件恢复明细。次日质控负责人按核账号查看当次实数及账实差。

## 一天的交接

1. 开班初始化来源库和离线库。来源初始化材料提供分区及首份盘点引用的既定修订。重复初始化保留两个库中经业务入口写入的内容。
2. 接纳正式盘点，以盘点号固定完整行及重数。同号同归属、同规范化内容的重接返回原号。
3. 在已有分区登记其余修订。修订身份由分区及修订号共同确定。
4. 登记具名差额。两个端点须已在同一分区声明，差额方向和变化都可按原号查对。
5. 档案员明确选择本次的修订、盘点号及差额号。发布在一次稳定读事务内取齐、核定并冻结这份选择。
6. 核定成立后，包和成功回执共同提交。凭回执中的发布包号领取当时的原字节。
7. 夜班把原件导入离线库，凭离线号及修订号恢复完整行。外站原格式件可以直接接纳。
8. 夜班按质控码核账，可提交账面计数，并把实数与账实差按核账号归档。来源后续更正和离线重开后，原账号仍返回当次结果。

## 运行

在仓库根目录使用 Python 3.11。项目只依赖标准库。

```sh
python3 -B -m unittest discover -s tests -t . -v
python3 -B demo.py
```

演示在独立临时库完成真实签发、关闭来源、离线接纳和核账重开。每条 `POINTWISE_SCENARIO` 记录含手算预期及实际下游结果。测试也使用各自的临时库。`examples/foreign-v1.json` 是独立编写的外站原件。

## Python 接口

用 `storage.open_database(path)` 管理 SQLite 连接，`path` 可为调用方指定的本地文件或 `:memory:`。下列业务写入口自行完成各自的事务，请在连接没有外层事务时调用。数量字段均为 Python `int`，身份文本均为非空 UTF-8 字符串。

| 入口 | 参数和结果 |
| --- | --- |
| `publication.commit.initialize_source` | `(db, partitions=(), initial_revisions=())`。后者为 `(partition, revision)` 对的可迭代对象。 |
| `inventory.accept.accept_inventory` | `(db, partition, revision, inventory_id, rows)` 返回盘点号。`inventory.store.get_inventory(db, partition, inventory_id)` 读原盘点。 |
| `revisions.register.register_revision` | `(db, partition, revision)` 返回声明修订号。 |
| `revisions.import_delta.accept_delta` | `(db, partition, delta_id, source, target, rows)` 返回差额号。`revisions.registry.get_delta(db, partition, delta_id)` 读原差额。 |
| `publication.commit.publish` | `(db, partition, revision_ids, inventory_ids, delta_ids)` 返回 `Receipt`，含 `receipt_id`、`package_id`、分区、修订及两类选件编号。每类选择内的编号唯一。 |
| `publication.receipts.fetch` | `(db, package_id)` 返回固定包字节。`publication.receipts.get_receipt(db, package_id)` 返回已存回执。 |
| `audit.store.initialize_offline` | `(db)` 初始化离线目录及核账存储。 |
| `offline.accept.import_package` | `(db, blob)` 返回本地离线包号。相同原字节重接返回原离线号。 |
| `offline.recover.recover` | `(db, package_id, revision)` 返回按完整键排序的四元组列表。 |
| `audit.reconcile.audit` | `(db, package_id, revision, ledger=None)` 返回已归档核账字典。 |
| `audit.export.fetch_audit` | `(db, audit_id)` 返回原归档核账字典。 |

发布号和离线号各自只在本地目录有意义。来源盘点号和差额号分属两个号段，各自在来源库内唯一。向同一号重交不同归属或内容会拒收，旧记录可继续使用。核账字典含 `audit_id`、`package_id`、`revision`、`actual`，提交账面时另含 `differences`。实数及差均按质控码升序排列。`ledger=None` 省略比较，`{}` 表示以零账面比较。差为实际减账面，覆盖两侧出现的代码，单侧缺项以零计。

一行是 `(station, slot, quality, count)`。前三项共同组成身份，最后一项以出现次数计。输入相同键相加，零项省略。正式盘点的每条输入计数须非负，可以提交空盘点。差额计数有符号，约定起点账加差额等于终点账。发布要求每个声明修订能经任一方向关联正式盘点，且全部盘点及差额能由同一组非负行账同时满足。恢复按站点、采样槽、质控码的字符串升序输出正重数。盘点与差额顺序或等价反向表示不改变恢复结果。

错误类型由 `storage` 提供。非法登记及账面输入报 `InputError`。非法选件、无盘点分量、互相矛盾或任一版有负重数时报其子类 `EvidenceError`。接纳坏格式报其子类 `PackageError`。合法类型的未知编号或未声明修订报 `NotFoundError`。发布中的 SQLite 错误转为 `StorageError`，包和回执一起回滚。旧包与原核账按号读取存档内容。格式错误及失败核账没有新增条目。

## 交接件 V1

包是单个 UTF-8 JSON 对象，字段恰为 `version`、`partition`、`revisions`、`inventories`、`deltas`。`version` 是整数 `1`，`revisions` 是非空的唯一修订号数组。盘点对象含 `id`、`revision`、`rows`，差额对象含 `id`、`source`、`target`、`rows`。`rows` 是零个或多个四元素数组，计数为 JSON 整数。每类证据内的编号各自唯一，全部引用均属于包内单一分区及显式声明范围。发布编码按编号和行键确定排序，接纳允许空白和排列差异并保存输入原字节。离线接纳校验格式、字段和内部引用。合法外站件还须满足与来源签发相同的全证据业务不变量。读回使用指定原件内的盘点和差额。

样例中 `X` 是 `ridge / 06:00 / G`，`Y` 是 `ridge / 07:00 / H`。A 有 `2X`，B→A 加 `X`，B→C 删 `X` 加 `Y`。逆推 B 有 `X`，再正推 C 有 `Y`。A→C 若删 `2X` 加 `Y`，可随同其余证据签发；若只删 `X` 加 `Y`，直达路线给出的 C 账多一个 `X`，整次拒发。
