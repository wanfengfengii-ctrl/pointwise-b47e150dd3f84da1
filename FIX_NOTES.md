# 修复说明（湖表盘点交接链路）

仅改动既有 Python/SQLite 链路，接口、V1 件格式、回执与目录号段均保持不变。

## 根因

1. `publication/reconcile.py` 的旧核定用 `setdefault(target, delta)` 每个终点只留一条差额，
   且在差额两端账目都已知时直接跳过，从不校验“另一条路线”是否与现有账目一致。
   因此 `d-ba + d-bc` 推出 C 只有 Y，而 `d-ac` 推出 C 另有一个 X 时，矛盾被吞掉，
   三差额仍拿到成功回执。同号修订上互相矛盾的第二张正式盘点同样不会被对出差异。
2. `offline/recover.py` 只沿 `target → source` 反向追边。请求 B 时，B 没有盘点锚点，
   而能到达 A 锚点的 `B→A` 边是从 B 出发的正向边，遍历不到，于是报
   “has no inventory”；C 同理。关闭来源连接后只剩 A 可读。
3. `offline/accept.py` 只做 V1 格式与引用校验，未对合法外站件执行全证据业务不变量，
   格式正确但账目矛盾的外站件本应拒发却可入库。

## 修复

- 新增统一求解器 `publication/reconcile.py::solve_accounts`：把修订当节点、差额当无向边，
  按连通分量从正式盘点锚点出发向两侧传播账目；随后逐条核对分量内**全部**差额方程
  （含构成另一条路线的回路边），再检查各修订重数非负、锚点账目与推导一致，
  且每个声明修订所在分量至少含一张正式盘点。任一不满足即抛 `EvidenceError`，
  发布在 `storage.atomic` 内整体回滚，`shipments` 与 `receipts` 均无新增。
- `reconcile_evidence` 与离线恢复共用该求解器：`offline/recover.py` 改为无向遍历，
  正、反向链都可关联到正式盘点，换序或等价反向表示结果不变，输出仍按完整键升序。
- `offline/accept.py` 在 `decode_package`（坏格式抛 `PackageError`）之后、入库事务之前
  调用同一 `reconcile_evidence`，业务矛盾抛 `EvidenceError` 且不留目录条目。
- 保留所选证据编号与方向：包编码仍按编号排序写入，外站原字节由
  `received_packages.blob` 原样保存，重接返回原离线号。

## 实际核验

- `python3 -B -m unittest discover -s tests -t . -v`：36 项全部通过
  （原 29 项断言全部保留，新增 `tests/test_evidence_invariants.py` 7 项回归：
  矛盾外站件拒发且无入库、无锚点修订拒发、负账拒发、坏格式仍为 `PackageError`、
  线上换序与等价反向恢复一致、同内容第二锚点仍合法）。
- INCIDENT.md 指定两项断言单独运行通过：
  `tests.test_publication_conflict...test_conflicting_paths`、
  `tests.test_offline.OfflineTests.test_reverse_recovery`。
- `python3 -B demo.py` 三条 `POINTWISE_SCENARIO` 全部与手算预期一致。
- 另用临时库端到端复演事故：三差额拒发且包/回执计数保持 (0,0)；仅选前两差额正常签发；
  关闭来源后离线对本地件与 `examples/foreign-v1.json` 读回
  A=`[('ridge','06:00','G',2)]`、B=`[('ridge','06:00','G',1)]`、
  C=`[('ridge','07:00','H',1)]`；后续更正与离线重开不改变原合法成果；
  10^4400 级大整数重数精确往返。
