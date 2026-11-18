# 青岚区盘点交接事故

交接范围为分区 `P` 的 A、B、C 三版。`X` 是 `ridge / 06:00 / G`，`Y` 是 `ridge / 07:00 / H`。正式盘点 `inv-a` 给出 A 有两次 X。

| 差额编号 | 起讫修订 | 完整行的重数变化 |
| --- | --- | --- |
| `d-ba` | B → A | X 加 1 |
| `d-bc` | B → C | X 减 1，Y 加 1 |
| `d-ac` | A → C | X 减 1，Y 加 1 |

前两张差额推得 B 有一次 X，C 有一次 Y。第三张却推得 C 有一次 X 和一次 Y。白班仍领到了包含三张差额的成功回执。三张差额同时选中时须拒发，包和成功回执均无新增。

只选前两张差额时应能正常签发。关闭来源连接并接纳该件后，夜班能读到 A，却读不出 B 或 C。按 A、B、C 顺序请求，正确明细分别为 `[('ridge', '06:00', 'G', 2)]`、`[('ridge', '06:00', 'G', 1)]` 和 `[('ridge', '07:00', 'H', 1)]`。独立的外站件 `examples/foreign-v1.json` 应能在同一离线入口得到相同明细。

在仓库根目录运行下列原业务断言。发布断言查拒发和目录，离线断言查本地签发件和独立外站件。业务偏差输出 `LAKE_HANDOFF_MISMATCH` 并返回非零状态，修复后两项均须通过。完整回归和真实交班演示沿 README.md 的入口运行。

```sh
python3 -B -m unittest -v tests.test_publication_conflict.PublicationConflictTests.test_conflicting_paths tests.test_offline.OfflineTests.test_reverse_recovery
```
